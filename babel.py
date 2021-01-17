import os
import sys
import subprocess

locale_path = os.path.join("downloadmagic", "locale")
template_path = os.path.join(locale_path, "downloadmagic.pot")
LANGUAGES = ["en", "es", "ja"]


def babel_extract() -> None:
    extract_command = [
        "pybabel",
        "extract",
        "-k",
        "T_",
        "-k",
        "TM_",
        "-o",
        template_path,
        "downloadmagic",
    ]
    subprocess.run(extract_command, check=True)


def babel_update() -> None:
    for language in LANGUAGES:
        update_command = [
            "pybabel",
            "update",
            "-D",
            "downloadmagic",
            "-d",
            locale_path,
            "-l",
            language,
            "-i",
            template_path,
        ]
        subprocess.run(update_command, check=True)


# pybabel compile -D downloadmagic -d downloadmagic\locale
def babel_compile() -> None:
    compile_command = [
        "pybabel",
        "compile",
        "-D",
        "downloadmagic",
        "-d",
        locale_path,
    ]
    subprocess.run(compile_command, check=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    action = args[0]
    if action == "extract":
        babel_extract()
    elif action == "update":
        babel_update()
    elif action == "compile":
        babel_compile()
