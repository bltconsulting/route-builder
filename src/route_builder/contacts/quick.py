"""One-argument contact PDF conversion for organizer use."""

import argparse
from pathlib import Path

from .cli import main as convert


def output_paths(pdf: Path) -> tuple[Path, Path]:
    if pdf.suffix.lower() != ".pdf":
        raise ValueError("Input must be a PDF file")
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")
    return (
        pdf.with_name(f"{pdf.stem}_contacts.csv"),
        pdf.with_name(f"{pdf.stem}_contacts_validation.json"),
    )


def find_pdf(value: Path) -> Path:
    if value.is_file() or value.parent != Path("."):
        return value
    local_downloads = Path.home() / "Downloads" / value.name
    if local_downloads.is_file():
        return local_downloads
    windows_users = Path("/mnt/c/Users")
    if windows_users.is_dir():
        for user_dir in windows_users.iterdir():
            if user_dir.name.casefold() == Path.home().name.casefold():
                windows_download = user_dir / "Downloads" / value.name
                if windows_download.is_file():
                    return windows_download
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parse-contact-pdf", description=__doc__)
    parser.add_argument("pdf", type=Path, help="PDF path (or filename in the current directory)")
    args = parser.parse_args(argv)
    pdf = find_pdf(args.pdf)
    try:
        csv_path, diagnostics_path = output_paths(pdf)
        for path in (csv_path, diagnostics_path):
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}")
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        parser.error(str(error))
    return convert([
        str(pdf), "--output", str(csv_path),
        "--diagnostics", str(diagnostics_path),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
