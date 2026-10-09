import os
import sys

def fix_cuda_paths():
    """Adds NVIDIA DLL dirs from pip packages to PATH on Windows.
    Solves 'Could not locate cudnn_ops64_9.dll' and similar issues."""
    if sys.platform != "win32":
        return

    import site
    packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        packages_dirs.append(site.getusersitepackages())

    for base in packages_dirs:
        for ndir in ("nvidia/cudnn/bin", "nvidia/cublas/bin",
                     "nvidia/cuda_runtime/bin", "nvidia/cuda_nvrtc/bin"):
            full_path = os.path.join(base, ndir)
            if os.path.exists(full_path):
                os.environ["PATH"] = full_path + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(full_path)
                    except Exception:
                        pass
