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

    def remote_is_dir(self, remote_path: str) -> bool:
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                attr = sftp.stat(remote_path)
                return self._is_dir_mode(attr.st_mode)
            except OSError:
                return False
            finally:
                sftp.close()
        finally:
            client.close()

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
        """Delete a book file and its sibling .sdr folder (supports subfolders)."""
        abs_path = self.resolve_under_documents(remote_name)
        parent = self._parent_dir(abs_path)
        stem = Path(remote_name).stem
        self.remove_remote(abs_path)
        self.remove_remote(f"{parent}/{stem}.sdr")

    def resolve_under_documents(self, relative: str = "") -> str:
        """Return absolute path under documents_dir; reject path traversal."""
        docs = self.documents_dir.rstrip("/")
        rel = (relative or "").replace("\\", "/").strip("/")
        if any(part == ".." for part in rel.split("/") if part):
            raise KindleError("Caminho inválido.")
        if not rel:
            return docs
        return f"{docs}/{rel}"

    def relative_to_documents(self, absolute: str) -> str:
        docs = self.documents_dir.rstrip("/")
        path = (absolute or "").replace("\\", "/").rstrip("/")
        if path == docs:
            return ""
        prefix = docs + "/"
        if not path.startswith(prefix):
            raise KindleError("Caminho fora de documents.")
        return path[len(prefix) :]

    def _is_dir_mode(self, st_mode: int) -> bool:
        return (st_mode & 0o170000) == 0o040000

    def list_dir(
        self,
        relative_path: str = "",
        extensions: set[str] | None = None,
    ) -> list[dict]:
        """List folders and book files in a documents subfolder (hides .sdr)."""
        extensions = {e.lower().lstrip(".") for e in (extensions or set())}
        abs_dir = self.resolve_under_documents(relative_path)
        client = self._connect()
        try:
            sftp = client.open_sftp()
            try:
                entries: list[dict] = []
                for attr in sftp.listdir_attr(abs_dir):
                    name = attr.filename
                    if name.startswith("."):
                        continue
                    if name.endswith(".sdr"):
                        continue
                    rel = f"{relative_path.strip('/')}/{name}".strip("/")
                    abs_path = f"{abs_dir.rstrip('/')}/{name}"
                    if self._is_dir_mode(attr.st_mode):
                        entries.append(
                            {
                                "name": name,
                                "type": "dir",
                                "rel": rel,
                                "path": abs_path,
                                "size": 0,
                                "mtime": int(attr.st_mtime or 0),
                            }
                        )
                        continue
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    if extensions and ext not in extensions:
                        continue
                    stem = Path(name).stem
                    cover_remote = f"{abs_dir}/{stem}.sdr/cover.jpg"
                    has_cover = False
                    try:
                        sftp.stat(cover_remote)
                        has_cover = True
                    except OSError:
                        try:
                            cover_remote = f"{abs_dir}/{stem}.sdr/cover.png"
                            sftp.stat(cover_remote)
                            has_cover = True
                        except OSError:
                            cover_remote = ""
                    entries.append(
                        {
                            "name": name,
                            "type": "file",
                            "rel": rel,
                            "path": abs_path,
                            "size": int(attr.st_size or 0),
                            "mtime": int(attr.st_mtime or 0),
                            "has_cover": has_cover,
                            "cover_remote": cover_remote,
                            "sdr_dir": f"{abs_dir}/{stem}.sdr",
                        }
                    )
                entries.sort(
                    key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].lower())
                )
                return entries
            finally:
                sftp.close()
        except KindleError:
            raise
        except (paramiko.SSHException, OSError) as exc:
            raise KindleError(f"Falha ao listar pasta: {exc}") from exc
        finally:
            client.close()

    def list_folder_tree(self) -> dict:
        """Return nested folder tree under documents (no .sdr)."""
        client = self._connect()
        try:
            sftp = client.open_sftp()

            def walk_sftp(rel: str) -> dict:
                abs_dir = self.resolve_under_documents(rel)
                children: list[dict] = []
                try:
                    attrs = sftp.listdir_attr(abs_dir)
                except OSError as exc:
                    raise KindleError(f"Falha ao ler árvore: {exc}") from exc
                dirs = []
                for attr in attrs:
                    name = attr.filename
                    if name.startswith(".") or name.endswith(".sdr"):
                        continue
                    if not self._is_dir_mode(attr.st_mode):
                        continue
                    dirs.append(name)
                dirs.sort(key=str.lower)
                for name in dirs:
                    child_rel = f"{rel}/{name}".strip("/")
                    children.append(walk_sftp(child_rel))
                return {
                    "name": Path(rel).name if rel else "documents",
                    "rel": rel,
                    "path": abs_dir,
                    "children": children,
                }

            try:
                return walk_sftp("")
            finally:
                sftp.close()
        finally:
            client.close()

    def mkdir(self, relative_path: str) -> str:
        abs_path = self.resolve_under_documents(relative_path)
        if abs_path == self.documents_dir.rstrip("/"):
            raise KindleError("Caminho de pasta inválido.")
        client = self._connect()
        try:
            self.ensure_remote_dir(client, abs_path)
        finally:
            client.close()
        return abs_path

    def rename_path(self, relative_path: str, new_name: str) -> str:
        new_name = (new_name or "").strip().replace("\\", "/").strip("/")
        if not new_name or "/" in new_name or new_name in (".", "..") or new_name.endswith(".sdr"):
            raise KindleError("Novo nome inválido.")
        src = self.resolve_under_documents(relative_path)
        if src == self.documents_dir.rstrip("/"):
            raise KindleError("Não é possível renomear a raiz documents.")
        parent = self._parent_dir(src)
        dest = f"{parent}/{new_name}"
        if self.remote_exists(dest):
            raise KindleError(f"Já existe: {new_name}")
        self._remote_mv(src, dest)
        return self.relative_to_documents(dest)

    def move_path(self, relative_src: str, relative_dest_dir: str) -> str:
        """Move a file or folder into dest dir (same volume rename)."""
        src = self.resolve_under_documents(relative_src)
        dest_dir = self.resolve_under_documents(relative_dest_dir)
        if src == self.documents_dir.rstrip("/"):
            raise KindleError("Não é possível mover a raiz documents.")
        name = Path(src).name
        src_norm = src.rstrip("/")
        dest_norm = dest_dir.rstrip("/")
        if dest_norm == src_norm or dest_norm.startswith(src_norm + "/"):
            raise KindleError("Não é possível mover uma pasta para dentro dela mesma.")
        dest = f"{dest_norm}/{name}"
        if dest == src:
            return self.relative_to_documents(src)
        if self.remote_exists(dest):
            raise KindleError(f"Destino já existe: {name}")
        self._remote_mv(src, dest)
        return self.relative_to_documents(dest)

    def move_document(self, relative_src: str, relative_dest_dir: str) -> str:
        """Move a book file and its sibling .sdr folder into dest dir."""
        src = self.resolve_under_documents(relative_src)
        dest_dir = self.resolve_under_documents(relative_dest_dir)
        name = Path(src).name
        stem = Path(name).stem
        src_parent = self._parent_dir(src)
        dest_file = f"{dest_dir.rstrip('/')}/{name}"
        if dest_file == src:
            return self.relative_to_documents(src)
        if self.remote_exists(dest_file):
            raise KindleError(f"Destino já existe: {name}")
        sdr_src = f"{src_parent}/{stem}.sdr"
        sdr_dest = f"{dest_dir.rstrip('/')}/{stem}.sdr"
        if self.remote_exists(sdr_src) and self.remote_exists(sdr_dest):
            raise KindleError(f"Pasta .sdr já existe no destino: {stem}.sdr")
        self._remote_mv(src, dest_file)
        if self.remote_exists(sdr_src):
            self._remote_mv(sdr_src, sdr_dest)
        return self.relative_to_documents(dest_file)

    def _remote_mv(self, src: str, dest: str) -> None:
        client = self._connect()
        try:
            dest_parent = self._parent_dir(dest)
            self.ensure_remote_dir(client, dest_parent)
            cmd = f'mv -- "{src}" "{dest}"'
            stdin, stdout, stderr = client.exec_command(cmd, timeout=self.timeout)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                err = stderr.read().decode("utf-8", errors="replace").strip()
                sftp = client.open_sftp()
                try:
                    sftp.rename(src, dest)
                except OSError as exc:
                    raise KindleError(
                        f"Falha ao mover {src} → {dest}: {err or exc}"
                    ) from exc
                finally:
                    sftp.close()
        finally:
            client.close()
