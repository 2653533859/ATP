export interface MobileApkSource {
  id: number
  filename: string
  package_name?: string | null
  version_name?: string | null
}

export interface MobileApkOption {
  label: string
  value: number
  packageName: string
  filename: string
}

/** 只把已确认包名的 APK 暴露给专项任务选择器，避免保存时才失败。 */
export function buildMobileApkOptions(apks: MobileApkSource[]): MobileApkOption[] {
  return apks.flatMap((apk) => {
    const packageName = apk.package_name?.trim()
    if (!packageName) return []
    const version = apk.version_name?.trim()
    return [{
      label: version ? `${packageName} · ${apk.filename} · v${version}` : `${packageName} · ${apk.filename}`,
      value: apk.id,
      packageName,
      filename: apk.filename,
    }]
  })
}

export function findMobileApkPackage(options: MobileApkOption[], apkId: number | null): string {
  if (apkId === null) return ''
  return options.find((option) => option.value === apkId)?.packageName ?? ''
}
