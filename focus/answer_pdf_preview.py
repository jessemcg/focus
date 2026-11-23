"""Private, session-local staging for printable answers."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import secrets
import stat

_PREVIEW_DIR = "focus-answer-pdfs"
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _require_private(fd: int) -> None:
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError("PDF preview directory is not private")


def _open_preview_dir(runtime: Path, *, create: bool = False) -> int:
    if runtime.anchor != "/" or runtime == Path("/") or ".." in runtime.parts:
        raise ValueError("No usable XDG_RUNTIME_DIR for PDF previews")
    # Walk with directory descriptors to reject symlinks at every level.
    fd = os.open("/", _DIR_FLAGS)
    try:
        for part in runtime.parts[1:]:
            child = os.open(part, _DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        _require_private(fd)
        if create:
            try:
                os.mkdir(_PREVIEW_DIR, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
        preview = os.open(_PREVIEW_DIR, _DIR_FLAGS, dir_fd=fd)
        try:
            _require_private(preview)
        except BaseException:
            os.close(preview)
            raise
        return preview
    finally:
        os.close(fd)


@dataclass
class StagedAnswerPDF:
    runtime: Path
    directory_fd: int
    staging_name: str | None
    final_name: str

    def publish(self) -> Path:
        """Publish only after the caller has revalidated its displayed answer."""
        if self.staging_name is None:
            raise RuntimeError("No staged answer PDF")
        current = _open_preview_dir(self.runtime)
        try:
            if not os.path.samestat(os.fstat(current), os.fstat(self.directory_fd)):
                raise PermissionError("PDF preview directory changed")
            os.replace(self.staging_name, self.final_name,
                       src_dir_fd=self.directory_fd, dst_dir_fd=self.directory_fd)
        finally:
            os.close(current)
        self.staging_name = None
        return self.runtime / _PREVIEW_DIR / self.final_name

    def close(self) -> None:
        try:
            if self.staging_name is not None:
                try:
                    os.unlink(self.staging_name, dir_fd=self.directory_fd)
                except FileNotFoundError:
                    pass
        finally:
            os.close(self.directory_fd)


def stage_answer_pdf(answer_id: str, markdown: str) -> StagedAnswerPDF:
    """Render privately off-thread; the caller must publish or close the result."""
    from .answer_pdf import PRINT_STYLE_VERSION, render_answer_pdf

    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
    digest = hashlib.sha256(PRINT_STYLE_VERSION + b"\0" + answer_id.encode("ascii")
                            + b"\0" + markdown.encode("utf-8")).hexdigest()
    fd = _open_preview_dir(runtime, create=True)
    staged = StagedAnswerPDF(runtime, fd, None, f"{digest}.pdf")
    try:
        name = f".stage-{secrets.token_hex(16)}"
        handle = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         mode=0o600, dir_fd=fd)
        staged.staging_name = name
        with os.fdopen(handle, "wb") as output:
            os.fchmod(output.fileno(), 0o600)
            render_answer_pdf(markdown, output)
    except BaseException:
        staged.close()
        raise
    return staged
