from locust import HttpUser, between, task


class AcceptanceUser(HttpUser):
    host = "http://http-target:8080"
    wait_time = between(0.1, 0.3)

    @task
    def health(self):
        self.client.get("/healthz", name="GET /healthz")
