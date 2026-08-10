from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path

import paramiko


class KindleError(Exception):
    """Raised when SCP/SSH to the Kindle fails."""


@dataclass
class KindleClient:
    host: str
    port: int
    username: str
    password: str
    timeout: int = 20
    remote_path: str = "/mnt/us/screensaver/current.png"
    refresh_cmd: str = ""
    clear_screensaver_dir: bool = True

    def _connect(self) -> paramiko.SSHClient:
        if not self.host:
            raise KindleError("KINDLE_HOST não configurado.")
        if not self.password:
            raise KindleError("KINDLE_PASSWORD não configurado.")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException as exc:
            raise KindleError("Falha de autenticação SSH (usuário/senha).") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise KindleError(
                f"Timeout ao conectar em {self.host}:{self.port}."
            ) from exc
        except (paramiko.SSHException, OSError, socket.error) as exc:
            raise KindleError(
                f"Não foi possível conectar em {self.host}:{self.port}: {exc}"
            ) from exc
        return client

    @property
    def remote_dir(self) -> str:
        return str(Path(self.remote_path).parent).replace("\\", "/")

    def ensure_remote_dir(self, client: paramiko.SSHClient) -> None:
        stdin, stdout, stderr = client.exec_command(
            f'mkdir -p "{self.remote_dir}"',
            timeout=self.timeout,
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err = stderr.read().decode("utf-8", errors="replace").strip()
            raise KindleError(f"Não foi possível criar pasta remota: {err or exit_status}")

    def clear_old_images(self, client: paramiko.SSHClient) -> None:
        """Keep only the new wallpaper so KOReader random_image always picks it."""
        if not self.clear_screensaver_dir:
            return
        # Remove common image types; leave the directory itself.
        cmd = (
            f'find "{self.remote_dir}" -maxdepth 1 -type f '
            r'\( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) -delete'
        )
        stdin, stdout, stderr = client.exec_command(cmd, timeout=self.timeout)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err = stderr.read().decode("utf-8", errors="replace").strip()
            raise KindleError(f"Não foi possível limpar pasta do screensaver: {err or exit_status}")

    def upload(self, local_path: Path) -> None:
        if not local_path.is_file():
            raise KindleError(f"Arquivo local não encontrado: {local_path}")

        client = self._connect()
        try:
            self.ensure_remote_dir(client)
            self.clear_old_images(client)
            sftp = client.open_sftp()
            try:
                sftp.put(str(local_path), self.remote_path)
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha no SCP: {exc}") from exc
        finally:
            client.close()

    def refresh(self) -> str | None:
        """Optional post-upload SSH command (empty = screensaver-only mode)."""
        if not self.refresh_cmd.strip():
            return None

        client = self._connect()
        try:
            stdin, stdout, stderr = client.exec_command(
                self.refresh_cmd,
                timeout=self.timeout,
            )
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if exit_status != 0:
                detail = err or out or f"exit {exit_status}"
                raise KindleError(f"Comando pós-envio falhou: {detail}")
            return out or "ok"
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha ao executar comando pós-envio: {exc}") from exc
        finally:
            client.close()

    def push(self, local_path: Path) -> dict[str, str]:
        self.upload(local_path)
        output = self.refresh()
        result = {
            "transferred": "ok",
            "screensaver_path": self.remote_path,
            "mode": "koreader_screensaver",
        }
        if output is not None:
            result["refresh_output"] = output
        return result
