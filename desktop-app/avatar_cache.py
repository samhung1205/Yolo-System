import os
import shutil


def cache_avatar_file(source_path, filename):
    if not source_path or not filename:
        return filename

    os.makedirs("user_avatars", exist_ok=True)
    target_path = os.path.join("user_avatars", filename)
    shutil.copyfile(source_path, target_path)
    return filename
