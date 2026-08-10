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
    password: str = ""
    key_path: str = ""
    timeout: int = 20
    remote_path: str = "/mnt/us/screensaver/current.png"
    refresh_cmd: str = ""
    clear_screensaver_dir: bool = True
    documents_dir: str = "/mnt/us/documents"

    def _connect(self) -> paramiko.SSHClient:
        if not self.host:
            raise KindleError("KINDLE_HOST não configurado.")

        key_file = self.key_path.strip()
        if key_file and not Path(key_file).is_file():
            key_file = ""

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "timeout": self.timeout,
            "allow_agent": False,
            "look_for_keys": False,
        }
        if key_file:
            connect_kwargs["key_filename"] = key_file
            if self.password:
                connect_kwargs["password"] = self.password
        else:
            connect_kwargs["password"] = self.password

        try:
            client.connect(**connect_kwargs)
        except paramiko.AuthenticationException as exc:
            raise KindleError(
                "Falha de autenticação SSH. "
                "Se no terminal não pede senha, copie a chave para secrets/id_rsa "
                "ou confirme se o Kindle aceita senha vazia."
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise KindleError(
                f"Timeout ao conectar em {self.host}:{self.port}."
            ) from exc
        except (paramiko.SSHException, OSError, socket.error) as exc:
            raise KindleError(
                f"Não foi possível conectar em {self.host}:{self.port}: {exc}"
            ) from exc
        return client

    @staticmethod
    def _parent_dir(remote_path: str) -> str:
        return str(Path(remote_path).parent).replace("\\", "/")

    def ensure_remote_dir(self, client: paramiko.SSHClient, remote_dir: str) -> None:
        stdin, stdout, stderr = client.exec_command(
            f'mkdir -p "{remote_dir}"',
            timeout=self.timeout,
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err = stderr.read().decode("utf-8", errors="replace").strip()
            raise KindleError(f"Não foi possível criar pasta remota: {err or exit_status}")

    def clear_old_images(self, client: paramiko.SSHClient, remote_dir: str) -> None:
        if not self.clear_screensaver_dir:
            return
        cmd = (
            f'find "{remote_dir}" -maxdepth 1 -type f '
            r'\( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) -delete'
        )
        stdin, stdout, stderr = client.exec_command(cmd, timeout=self.timeout)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err = stderr.read().decode("utf-8", errors="replace").strip()
            raise KindleError(f"Não foi possível limpar pasta do screensaver: {err or exit_status}")

    def upload_to(
        self,
        local_path: Path,
        remote_path: str,
        *,
        clear_images: bool = False,
    ) -> None:
        if not local_path.is_file():
            raise KindleError(f"Arquivo local não encontrado: {local_path}")

        remote_dir = self._parent_dir(remote_path)
        client = self._connect()
        try:
            self.ensure_remote_dir(client, remote_dir)
            if clear_images:
                self.clear_old_images(client, remote_dir)
            sftp = client.open_sftp()
            try:
                sftp.put(str(local_path), remote_path)
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha no SCP: {exc}") from exc
        finally:
            client.close()

    def upload(self, local_path: Path) -> None:
        self.upload_to(
            local_path,
            self.remote_path,
            clear_images=self.clear_screensaver_dir,
        )

    def upload_document(self, local_path: Path, remote_name: str) -> str:
        remote_name = remote_name.lstrip("/")
        remote_path = f"{self.documents_dir.rstrip('/')}/{remote_name}"
        self.upload_to(local_path, remote_path, clear_images=False)
        return remote_path

    def refresh(self) -> str | None:
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

    def push_document(
        self,
        local_path: Path,
        remote_name: str,
        *,
        cover_local: Path | None = None,
    ) -> dict[str, str]:
        remote_path = self.upload_document(local_path, remote_name)
        result = {
            "transferred": "ok",
            "documents_path": remote_path,
            "mode": "kindle_documents",
        }
        if cover_local is not None and cover_local.is_file():
            stem = Path(remote_name).stem
            cover_remote = (
                f"{self.documents_dir.rstrip('/')}/{stem}.sdr/cover.jpg"
            )
            self.upload_to(cover_local, cover_remote, clear_images=False)
            result["cover_path"] = cover_remote
        return result

    def list_documents(self, extensions: set[str] | None = None) -> list[dict]:
        """List book files in documents_dir (not .sdr folders)."""
        extensions = {e.lower().lstrip(".") for e in (extensions or set())}
        docs = self.documents_dir.rstrip("/")
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                entries = []
                for attr in sftp.listdir_attr(docs):
                    name = attr.filename
                    if name.startswith("."):
                        continue
                    if name.endswith(".sdr"):
                        continue
                    # skip directories
                    if (attr.st_mode & 0o170000) == 0o040000:
                        continue
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    if extensions and ext not in extensions:
                        continue
                    stem = Path(name).stem
                    cover_remote = f"{docs}/{stem}.sdr/cover.jpg"
                    has_cover = False
                    try:
                        sftp.stat(cover_remote)
                        has_cover = True
                    except OSError:
                        # try cover.png
                        try:
                            sftp.stat(f"{docs}/{stem}.sdr/cover.png")
                            has_cover = True
                            cover_remote = f"{docs}/{stem}.sdr/cover.png"
                        except OSError:
                            cover_remote = ""
                    entries.append(
                        {
                            "name": name,
                            "path": f"{docs}/{name}",
                            "size": int(attr.st_size or 0),
                            "mtime": int(attr.st_mtime or 0),
                            "has_cover": has_cover,
                            "cover_remote": cover_remote,
                            "sdr_dir": f"{docs}/{stem}.sdr",
                        }
                    )
                entries.sort(key=lambda e: e["name"].lower())
                return entries
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha ao listar documents: {exc}") from exc
        finally:
            client.close()

    def download_file(self, remote_path: str, local_path: Path) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                sftp.get(remote_path, str(local_path))
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha ao baixar {remote_path}: {exc}") from exc
        finally:
            client.close()
        return local_path

    def remote_exists(self, remote_path: str) -> bool:
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                sftp.stat(remote_path)
                return True
            except OSError:
                return False
            finally:
                sftp.close()
        finally:
            client.close()

    def read_text(self, remote_path: str) -> str:
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                with sftp.open(remote_path, "r") as fh:
                    data = fh.read()
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="replace")
                return str(data)
            except OSError as exc:
                raise KindleError(f"Não foi possível ler {remote_path}: {exc}") from exc
            finally:
                sftp.close()
        finally:
            client.close()

    def write_text(self, remote_path: str, content: str, *, backup: bool = True) -> None:
        remote_dir = self._parent_dir(remote_path)
        client = self._connect()
        try:
            self.ensure_remote_dir(client, remote_dir)
            sftp = client.open_sftp()
            try:
                if backup:
                    try:
                        sftp.stat(remote_path)
                        try:
                            sftp.remove(remote_path + ".old")
                        except OSError:
                            pass
                        sftp.rename(remote_path, remote_path + ".old")
                    except OSError:
                        pass
                with sftp.open(remote_path, "w") as fh:
                    fh.write(content.encode("utf-8"))
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha ao gravar {remote_path}: {exc}") from exc
        finally:
            client.close()

    def remove_remote(self, remote_path: str) -> None:
        """Remove a file or directory tree on the Kindle."""
        client = self._connect()
        try:
            # Prefer rm -rf via shell for .sdr directories
            cmd = f'rm -rf -- "{remote_path}"'
            stdin, stdout, stderr = client.exec_command(cmd, timeout=self.timeout)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                err = stderr.read().decode("utf-8", errors="replace").strip()
                raise KindleError(f"Falha ao apagar {remote_path}: {err or exit_status}")
        finally:
            client.close()

    def delete_document(self, remote_name: str) -> None:
        docs = self.documents_dir.rstrip("/")
        name = remote_name.lstrip("/")
        stem = Path(name).stem
        self.remove_remote(f"{docs}/{name}")
        self.remove_remote(f"{docs}/{stem}.sdr")
