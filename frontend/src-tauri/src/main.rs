#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Duration;
use tauri::Manager;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

fn powershell_path(path: PathBuf) -> PathBuf {
    let text = path.to_string_lossy();
    if let Some(unc) = text.strip_prefix(r"\\?\UNC\") {
        return PathBuf::from(format!(r"\\{unc}"));
    }
    if let Some(local) = text.strip_prefix(r"\\?\") {
        return PathBuf::from(local);
    }
    path
}

fn local_runtime_is_ready() -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], 8001));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_secs(3)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(3)));
    if stream
        .write_all(
            b"GET /api/v1/runtime HTTP/1.1\r\nHost: 127.0.0.1:8001\r\nConnection: close\r\n\r\n",
        )
        .is_err()
    {
        return false;
    }
    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    let Some((headers, body)) = response.split_once("\r\n\r\n") else {
        return false;
    };
    if !headers.starts_with("HTTP/1.1 200 ") {
        return false;
    }
    let Ok(info) = serde_json::from_str::<serde_json::Value>(body) else {
        return false;
    };
    info["mode"] == "local" && info["database"] == "sqlite" && info["storage"] == "filesystem"
}

fn start_local_backend(resources: &Path, state_root: &Path) -> Result<(), String> {
    let script = resources.join("scripts").join("windows-standalone.ps1");
    if !script.is_file() {
        return Err("missing local backend launcher".into());
    }
    std::fs::create_dir_all(state_root).map_err(|e| e.to_string())?;
    let mut command = Command::new("powershell.exe");
    command
        .args(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
        .arg(script)
        .args(["-Action", "ensure", "-Frontend", "static", "-StateRoot"])
        .arg(state_root);
    #[cfg(windows)]
    command.creation_flags(0x08000000);
    let log =
        std::fs::File::create(state_root.join("desktop-startup.log")).map_err(|e| e.to_string())?;
    let error_log = log.try_clone().map_err(|e| e.to_string())?;
    command
        .stdout(Stdio::from(log))
        .stderr(Stdio::from(error_log));
    let status = command.status().map_err(|e| e.to_string())?;
    if !status.success() {
        return Err("local backend startup failed".into());
    }
    if !local_runtime_is_ready() {
        return Err("local runtime verification failed".into());
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .ok_or("desktop window missing")?;
            let resources = powershell_path(app.path().resource_dir()?);
            let state_root = std::env::var_os("LOCALAPPDATA")
                .map(PathBuf::from)
                .ok_or("LOCALAPPDATA missing")?
                .join("ATP")
                .join("Desktop");
            std::thread::spawn(move || {
                let ready = start_local_backend(&resources, &state_root).is_ok();
                let navigated = ready
                    && window
                        .navigate("http://127.0.0.1:8001/".parse().expect("valid local URL"))
                        .is_ok();
                if !navigated {
                    // The embedded startup page may not have finished loading yet.
                    for _ in 0..5 {
                        let _ = window.eval("window.atpStartupFailed && window.atpStartupFailed()");
                        std::thread::sleep(Duration::from_millis(300));
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::powershell_path;
    use std::path::PathBuf;

    #[test]
    fn powershell_paths_accept_windows_long_path_prefixes() {
        assert_eq!(
            powershell_path(PathBuf::from(r"\\?\E:\ATP\app")),
            PathBuf::from(r"E:\ATP\app")
        );
        assert_eq!(
            powershell_path(PathBuf::from(r"\\?\UNC\server\share\app")),
            PathBuf::from(r"\\server\share\app")
        );
        assert_eq!(
            powershell_path(PathBuf::from(r"D:\ATP\app")),
            PathBuf::from(r"D:\ATP\app")
        );
    }
}
