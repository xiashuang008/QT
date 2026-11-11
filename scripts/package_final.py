from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


OUTPUT_NAME = "25260660028-final-project.zip"
REQUIRED_ENTRIES = (
    ".git/HEAD",
    "README.md",
    "requirements.txt",
    "docs/02-architecture.md",
    "docs/images/02-architecture-workflow.png",
    "docs/images/02-architecture-states.png",
)


def should_exclude(relative_path):
    parts = relative_path.parts
    # output/ 是运行时产物；__pycache__ 与 .pyc 是编译缓存
    # .workbuddy/ 是 AI 助手的本地记忆目录，不属于项目交付物
    excluded_dirs = ("output", "__pycache__", ".workbuddy")
    return any(part in excluded_dirs for part in parts) or relative_path.suffix == ".pyc"


def package_project():
    project_root = Path(__file__).resolve().parents[1]
    destination = project_root.parent / OUTPUT_NAME
    files = [
        path
        for path in project_root.rglob("*")
        if path.is_file() and not should_exclude(path.relative_to(project_root))
    ]

    # 不能用 Compress-Archive -Path *（会丢 .git/），也不能用 git archive（会省略历史）。
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(files, key=lambda item: item.relative_to(project_root).as_posix()):
            archive.write(path, path.relative_to(project_root).as_posix())

    with ZipFile(destination, "r") as archive:
        names = archive.namelist()
        git_count = sum(name.startswith(".git/") for name in names)
        has_shallow = ".git/shallow" in names
        required = {name: name in names for name in REQUIRED_ENTRIES}

    print(f"压缩包路径：{destination}")
    print(f"条目总数：{len(names)}")
    print(f".git/ 条目数：{git_count}")
    print(f"是否存在 .git/shallow：{has_shallow}")
    for name, present in required.items():
        print(f"是否包含 {name}：{present}")

    if has_shallow:
        raise RuntimeError("检测到 .git/shallow，浅拷贝不合格")
    missing = [name for name, present in required.items() if not present]
    if missing:
        raise RuntimeError(f"压缩包缺少必需条目：{missing}")
    if git_count == 0:
        raise RuntimeError("压缩包未包含 .git/ 条目")
    return destination


def main():
    package_project()


if __name__ == "__main__":
    main()
