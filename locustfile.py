from locust import HttpUser, task, between


class UsuarioNavegador(HttpUser):
    wait_time = between(1, 3)

    @task
    def ver_estado(self):
        self.client.get("/health")


class UsuarioComprador(HttpUser):
    wait_time = between(1, 3)

    @task
    def procesar(self):
        self.client.post("/procesar", json={"texto": "pedido"})