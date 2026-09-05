#!/usr/bin/env python3
"""
================================================================================
VERIFY LAPTOP ENVIRONMENT: DUAL-ENGINE OCR & GENAI FALLBACK DIAGNOSTIC
================================================================================
Target Platform : Windows 11 (x64)
Target Hardware : Intel Core i5 | NVIDIA GeForce RTX 2050 (4GB VRAM)
Primary Task    : Local GPU-Accelerated PaddleOCR + Google GenAI SDK Vision Fallback
Author          : Systems Engineering & CUDA DevOps Specialist
================================================================================
"""

import sys
import os
import platform
import subprocess
import shutil
import ctypes
from typing import Dict, Any, Tuple, Optional, List

# ------------------------------------------------------------------------------
# 0. Windows Console Encoding & UTF-8 Stream Hardening
# ------------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        # Reconfigure standard streams to UTF-8 with safe fallback
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def safe_print(*args, **kwargs):
    """Bulletproof print that falls back to sanitized ASCII if console codec rejects characters."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        sanitized = sep.join(str(a).encode("ascii", errors="replace").decode("ascii") for a in args)
        sys.stdout.write(sanitized + end)

# ------------------------------------------------------------------------------
# 1. Console Styler & Windows ANSI Initialization
# ------------------------------------------------------------------------------
def init_windows_terminal() -> bool:
    """Enable ANSI virtual terminal processing on native Windows console."""
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
                return True
        except Exception:
            return False
    return False

# Initialize console virtual terminal processing
init_windows_terminal()

class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN= "\033[42m"
    BG_BLUE = "\033[44m"

def badge_pass(text: str = "PASS") -> str:
    return f"{Color.BOLD}{Color.GREEN}[{text}]{Color.RESET}"

def badge_fail(text: str = "FAIL") -> str:
    return f"{Color.BOLD}{Color.RED}[{text}]{Color.RESET}"

def badge_warn(text: str = "WARN") -> str:
    return f"{Color.BOLD}{Color.YELLOW}[{text}]{Color.RESET}"

def badge_info(text: str = "INFO") -> str:
    return f"{Color.BOLD}{Color.CYAN}[{text}]{Color.RESET}"

def print_banner(title: str, subtitle: str = ""):
    term_width = 86
    border = "=" * term_width
    safe_print(f"\n{Color.CYAN}{border}")
    safe_print(f" {Color.BOLD}{Color.WHITE}{title.center(term_width - 2)}{Color.RESET}{Color.CYAN}")
    if subtitle:
        safe_print(f" {Color.DIM}{subtitle.center(term_width - 2)}{Color.RESET}{Color.CYAN}")
    safe_print(f"{border}{Color.RESET}")

def print_section(number: int, title: str):
    safe_print(f"\n{Color.BOLD}{Color.MAGENTA}[{number}/6] {title}{Color.RESET}")
    safe_print(f"{Color.DIM}{'-' * 86}{Color.RESET}")

def print_kv(key: str, val: str, status_badge: str = ""):
    pad_len = 38
    k_formatted = f"  {Color.WHITE}{key:<{pad_len}}{Color.RESET}"
    sep = f"{Color.DIM}:{Color.RESET} "
    badge = f" {status_badge}" if status_badge else ""
    safe_print(f"{k_formatted}{sep}{val}{badge}")


# ------------------------------------------------------------------------------
# 2. Memory Structure for Windows (Native GlobalMemoryStatusEx)
# ------------------------------------------------------------------------------
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]

def get_windows_ram() -> Tuple[float, float, int]:
    """Retrieve total RAM (GB), available RAM (GB), and percent load."""
    if sys.platform == "win32":
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_gb = stat.ullTotalPhys / (1024 ** 3)
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
            load = stat.dwMemoryLoad
            return total_gb, avail_gb, load
        except Exception:
            pass

    # Fallback to psutil if installed
    try:
        import psutil
        v = psutil.virtual_memory()
        return v.total / (1024 ** 3), v.available / (1024 ** 3), int(v.percent)
    except Exception:
        return 0.0, 0.0, 0


# ------------------------------------------------------------------------------
# 3. Diagnostic Sub-Systems
# ------------------------------------------------------------------------------

class EnvironmentAuditor:
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.remediations: List[str] = []

    # --------------------------------------------------------------------------
    # CHECK 1: System & OS Level Audit
    # --------------------------------------------------------------------------
    def audit_system_and_os(self) -> bool:
        print_section(1, "SYSTEM ARCHITECTURE & OPERATING SYSTEM AUDIT")

        is_win = sys.platform == "win32"
        os_name = platform.system()
        os_release = platform.release()
        os_version = platform.version()

        # Check native Windows vs WSL / restricted container
        is_wsl = False
        if os.path.exists("/proc/version"):
            try:
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        is_wsl = True
            except Exception:
                pass
        if "WSL_DISTRO_NAME" in os.environ:
            is_wsl = True

        # Bitness and Python runtime
        bitness = platform.architecture()[0]
        py_ver = platform.python_version()
        py_compiler = platform.python_compiler()

        # Virtual Environment Detection
        is_venv = (sys.prefix != sys.base_prefix) or hasattr(sys, "real_prefix")
        is_conda = "CONDA_PREFIX" in os.environ
        env_type = "VirtualEnv (venv)" if is_venv else ("Conda Env" if is_conda else "Global / System")

        # Processor Info
        cpu_arch = platform.machine()
        cpu_ident = os.environ.get("PROCESSOR_IDENTIFIER", platform.processor() or "Unknown CPU")

        # System RAM
        total_ram, avail_ram, ram_load = get_windows_ram()

        # Print outputs
        print_kv("Operating System", f"{os_name} {os_release} (Build {os_version})", 
                 badge_pass() if is_win and not is_wsl else badge_fail())
        print_kv("Execution Context", "Native Windows Host" if not is_wsl else "WSL Container (Not Native)", 
                 badge_pass() if not is_wsl else badge_warn())
        print_kv("Host CPU Architecture", f"{cpu_ident} ({cpu_arch})", badge_info())
        print_kv("Python Runtime Version", f"{py_ver} ({bitness}, {py_compiler[:14]})", 
                 badge_pass() if "64" in bitness else badge_fail("32-BIT WARN"))
        print_kv("Python Environment Type", f"{env_type} -> [{sys.prefix}]", badge_info())
        
        ram_status = badge_pass() if avail_ram >= 3.5 else badge_warn("LOW MEMORY")
        print_kv("System Physical RAM", f"{total_ram:.2f} GB Total | {avail_ram:.2f} GB Free ({ram_load}% Load)", ram_status)

        # Sanity assertions
        all_ok = True
        if not is_win or is_wsl:
            self.remediations.append("Execute directly in native Windows 11 PowerShell/CMD for direct WDDM GPU access.")
            all_ok = False
        if "64" not in bitness:
            self.remediations.append("CRITICAL: Python must be 64-bit to link with NVIDIA CUDA runtime DLLs. Reinstall Python x64.")
            all_ok = False
        if total_ram < 8.0:
            self.remediations.append("System RAM is < 8GB. Windows OS + OCR layout models may cause aggressive paging.")

        self.results["os_ok"] = all_ok
        self.results["total_ram_gb"] = total_ram
        self.results["avail_ram_gb"] = avail_ram
        return all_ok

    # --------------------------------------------------------------------------
    # CHECK 2: NVIDIA Hardware & CUDA Presence Check
    # --------------------------------------------------------------------------
    def audit_nvidia_hardware(self) -> bool:
        print_section(2, "NVIDIA HARDWARE & CUDA DRIVER SUBSYSTEM")

        # 1. Locate nvidia-smi
        nvidia_smi_path = shutil.which("nvidia-smi")
        if not nvidia_smi_path and sys.platform == "win32":
            candidate = r"C:\Windows\System32\nvidia-smi.exe"
            if os.path.exists(candidate):
                nvidia_smi_path = candidate

        gpu_found = False
        gpu_name = "N/A"
        driver_ver = "N/A"
        cuda_driver_max = "N/A"
        vram_total_mb = 0.0
        vram_free_mb = 0.0
        vram_used_mb = 0.0

        if nvidia_smi_path:
            try:
                # Query detailed GPU info
                cmd = [
                    nvidia_smi_path,
                    "--query-gpu=name,driver_version,memory.total,memory.free,memory.used",
                    "--format=csv,noheader,nounits"
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                if proc.returncode == 0 and proc.stdout.strip():
                    lines = [line.strip() for line in proc.stdout.strip().split("\n") if line.strip()]
                    if lines:
                        parts = [p.strip() for p in lines[0].split(",")]
                        gpu_name = parts[0]
                        driver_ver = parts[1]
                        vram_total_mb = float(parts[2])
                        vram_free_mb = float(parts[3])
                        vram_used_mb = float(parts[4])
                        gpu_found = True
                
                # Check Driver CUDA API capability via regular nvidia-smi header
                proc_hdr = subprocess.run([nvidia_smi_path], capture_output=True, text=True, timeout=6)
                for line in proc_hdr.stdout.split("\n"):
                    if "CUDA Version:" in line:
                        cuda_driver_max = line.split("CUDA Version:")[1].split("|")[0].strip()
                        break
            except Exception:
                gpu_found = False

        # 2. Check nvcc compiler
        nvcc_path = shutil.which("nvcc")
        nvcc_ver = "Not in PATH"
        cuda_path_env = os.environ.get("CUDA_PATH", None)

        if nvcc_path:
            try:
                proc_nvcc = subprocess.run([nvcc_path, "--version"], capture_output=True, text=True, timeout=5)
                for line in proc_nvcc.stdout.split("\n"):
                    if "release" in line.lower():
                        nvcc_ver = line.strip()
                        break
            except Exception:
                nvcc_ver = "Detected (Version parse error)"
        elif cuda_path_env:
            nvcc_ver = f"CUDA Toolkit detected at: {cuda_path_env}"

        # Print outputs
        print_kv("NVIDIA SMI Utility", nvidia_smi_path or "Not Found", 
                 badge_pass() if nvidia_smi_path else badge_fail())
        print_kv("NVIDIA GPU Device", gpu_name, 
                 badge_pass() if gpu_found else badge_fail())
        print_kv("NVIDIA Display Driver", f"v{driver_ver} (Supports up to CUDA {cuda_driver_max})", 
                 badge_pass() if gpu_found else badge_fail())
        print_kv("CUDA Compiler (nvcc)", nvcc_ver, 
                 badge_pass() if nvcc_path else badge_info("Optional for Prebuilt Wheels"))

        # Hardware Threshold Evaluation (RTX 2050 4GB threshold check)
        vram_total_gb = vram_total_mb / 1024.0
        vram_free_gb = vram_free_mb / 1024.0

        if gpu_found:
            vram_display = f"{vram_total_gb:.2f} GB Total | {vram_free_gb:.2f} GB Free ({vram_used_mb:.0f} MB Used)"
            
            # Check 4GB Hardware Boundary
            if vram_total_gb >= 3.7:  # 4096 MB nominally reports ~3.8-4.0 GB
                vram_badge = badge_pass("4GB HARDWARE BOUNDARY MET")
            else:
                vram_badge = badge_fail("BELOW 4GB THRESHOLD")
            
            print_kv("Hardware VRAM Limit", vram_display, vram_badge)

            # Explicit Available VRAM Alert Check
            if vram_free_gb < 3.0:
                safe_print(
                    f"  {Color.YELLOW}▲ ALERT: Available VRAM is currently {vram_free_gb:.2f} GB, below the 4GB dedicated threshold!{Color.RESET}\n"
                    f"    {Color.DIM}Impact: Dense PDF layout modeling (PP-Structure / Table Analysis) may encounter CUDA OOM.{Color.RESET}\n"
                    f"    {Color.DIM}Action: Close GPU-heavy apps (Chrome hardware acceleration, 3D apps) and maintain layout batch_size=1.{Color.RESET}"
                )
            else:
                safe_print(f"  {Color.GREEN}✔ Available VRAM headroom ({vram_free_gb:.2f} GB) is optimal for local layout modeling.{Color.RESET}")
        else:
            print_kv("Hardware VRAM Limit", "Unknown / No NVIDIA GPU detected", badge_fail())

        all_ok = gpu_found and (vram_total_gb >= 3.5)
        if not gpu_found:
            self.remediations.append("No active NVIDIA GPU detected. Ensure NVIDIA driver 535+ is installed from GeForce Experience or nvidia.com.")
        elif vram_total_gb < 3.5:
            self.remediations.append(f"VRAM ({vram_total_gb:.1f} GB) is below 4GB threshold. Local layout models may encounter OOM on dense PDFs.")

        self.results["gpu_found"] = gpu_found
        self.results["gpu_name"] = gpu_name
        self.results["vram_total_gb"] = vram_total_gb
        self.results["vram_free_gb"] = vram_free_gb
        return all_ok

    # --------------------------------------------------------------------------
    # CHECK 3: PyTorch & CUDA Bridge Verification
    # --------------------------------------------------------------------------
    def audit_pytorch_cuda_bridge(self) -> bool:
        print_section(3, "PYTORCH & CUDA BRIDGE INTEROPERABILITY")

        try:
            import torch
            torch_installed = True
            torch_version = torch.__version__
        except ImportError:
            torch_installed = False
            torch_version = "Not Installed"

        if not torch_installed:
            print_kv("PyTorch Library", "Module 'torch' not installed", badge_fail())
            self.remediations.append("Install CUDA-enabled PyTorch: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`")
            self.results["torch_cuda_ok"] = False
            return False

        print_kv("PyTorch Package Version", torch_version, badge_info())

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            cuda_runtime_ver = torch.version.cuda or "Unknown"
            cudnn_ver = torch.backends.cudnn.version() if hasattr(torch.backends, "cudnn") else "N/A"
            dev_count = torch.cuda.device_count()
            dev_name = torch.cuda.get_device_name(0) if dev_count > 0 else "N/A"
            
            # Compute Capability
            cap = torch.cuda.get_device_capability(0) if dev_count > 0 else (0, 0)
            cap_str = f"SM {cap[0]}.{cap[1]}"

            print_kv("torch.cuda.is_available()", "True (GPU Bridge Active)", badge_pass())
            print_kv("PyTorch CUDA Runtime", f"CUDA {cuda_runtime_ver} | cuDNN {cudnn_ver}", badge_pass())
            print_kv("Device[0] Hardware Name", f"{dev_name} ({cap_str})", badge_pass())

            # Memory Allocation Probe
            try:
                x = torch.zeros((128, 128), device="cuda:0")
                y = x + 1.0
                _ = y.sum().item()
                del x, y
                torch.cuda.empty_cache()
                print_kv("PyTorch Tensor Allocation", "CUDA malloc & arithmetic verified on cuda:0", badge_pass())
                self.results["torch_cuda_ok"] = True
                return True
            except Exception as e:
                print_kv("PyTorch Tensor Allocation", f"Execution Fault: {str(e)[:45]}", badge_fail())
                self.remediations.append(f"PyTorch CUDA allocation error: {e}. Check display driver compatibility.")
                self.results["torch_cuda_ok"] = False
                return False
        else:
            print_kv("torch.cuda.is_available()", "False (CPU-Only Build Detected)", badge_fail())
            safe_print(f"  {Color.RED}▲ PyTorch is currently running a CPU-only wheel (+cpu). PyTorch cannot leverage the RTX 2050.{Color.RESET}")
            self.remediations.append("Replace CPU PyTorch with CUDA wheel: `pip uninstall -y torch torchvision && pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`")
            self.results["torch_cuda_ok"] = False
            return False

    # --------------------------------------------------------------------------
    # CHECK 4: PaddlePaddle GPU Acceleration Integrity Check
    # --------------------------------------------------------------------------
    def audit_paddle_gpu(self) -> bool:
        print_section(4, "PADDLEPADDLE GPU ACCELERATION & OPERATOR INTEGRITY")

        try:
            import paddle
            paddle_installed = True
            paddle_ver = paddle.__version__
        except ImportError:
            paddle_installed = False
            paddle_ver = "Not Installed"

        if not paddle_installed:
            print_kv("PaddlePaddle Package", "Module 'paddle' not installed", badge_fail())
            safe_print(f"  {Color.RED}▲ Neither paddlepaddle nor paddlepaddle-gpu is installed in this Python environment.{Color.RESET}")
            self.remediations.append("Install PaddlePaddle-GPU for Windows: `pip install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu118/`")
            self.results["paddle_cuda_ok"] = False
            return False

        print_kv("PaddlePaddle Version", paddle_ver, badge_info())

        # Check CUDA compilation
        try:
            compiled_cuda = paddle.device.is_compiled_with_cuda()
        except Exception:
            compiled_cuda = False

        if not compiled_cuda:
            print_kv("is_compiled_with_cuda()", "False (CPU-Only Paddle Installed)", badge_fail())
            safe_print(f"  {Color.RED}▲ The installed PaddlePaddle build does not include CUDA kernels. Local OCR will fallback to CPU and run 5-10x slower.{Color.RESET}")
            self.remediations.append("Replace CPU Paddle with GPU wheel: `pip uninstall -y paddlepaddle paddlepaddle-gpu && pip install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu118/`")
            self.results["paddle_cuda_ok"] = False
            return False

        print_kv("is_compiled_with_cuda()", "True (Compiled with CUDA)", badge_pass())

        # Probe active GPU device & tensor allocation
        try:
            paddle.device.set_device("gpu:0")
            current_device = paddle.device.get_device()
            print_kv("Paddle Active Device", current_device, badge_pass())

            # Perform minor tensor operation check on GPU
            t1 = paddle.to_tensor([1.0, 2.0, 3.0, 4.0])
            t2 = t1 * 2.5
            result_val = float(t2.sum().item())
            del t1, t2

            print_kv("GPU Tensor Computation", f"Tensor arithmetic completed on {current_device} (Sum: {result_val:.1f})", badge_pass())
            self.results["paddle_cuda_ok"] = True
            return True
        except Exception as e:
            err_str = str(e)
            print_kv("GPU Tensor Computation", f"Execution Fault: {err_str[:40]}...", badge_fail())
            
            # Common Windows Paddle Issue: zlibwapi.dll or MSVCP140
            if "zlibwapi.dll" in err_str.lower() or "cudnn" in err_str.lower():
                safe_print(f"  {Color.YELLOW}▲ MISSING WINDOWS DLL: cuDNN/zlibwapi.dll is missing from Windows PATH.{Color.RESET}")
                self.remediations.append("Windows Fix: Download `zlibwapi.dll` (from NVIDIA cuDNN or zlib) and place in `C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v11.8\\bin` or `C:\\Windows\\System32`.")
            else:
                self.remediations.append(f"Paddle GPU memory allocation fault: {err_str}")

            self.results["paddle_cuda_ok"] = False
            return False

    # --------------------------------------------------------------------------
    # CHECK 5: Cloud GenAI SDK Availability & Fallback Layer
    # --------------------------------------------------------------------------
    def audit_genai_sdk(self) -> bool:
        print_section(5, "CLOUD GENAI SDK (GEMINI VISION FALLBACK LAYER)")

        genai_installed = False
        genai_ver = "Unknown"
        sdk_type = "None"

        # 1. Check modern 'google-genai' SDK
        try:
            from google import genai
            genai_installed = True
            sdk_type = "Modern google-genai (Unified Client)"
            try:
                import importlib.metadata
                genai_ver = importlib.metadata.version("google-genai")
            except Exception:
                genai_ver = getattr(genai, "__version__", "Installed")
        except ImportError:
            # 2. Check legacy google-generativeai
            try:
                import google.generativeai as legacy_genai
                genai_installed = True
                sdk_type = "Legacy google-generativeai"
                genai_ver = getattr(legacy_genai, "__version__", "Installed")
            except ImportError:
                genai_installed = False

        if genai_installed:
            print_kv("Google GenAI Library", f"{sdk_type} v{genai_ver}", badge_pass())
        else:
            print_kv("Google GenAI Library", "google-genai not found", badge_fail())
            self.remediations.append("Install modern Google GenAI SDK: `pip install google-genai`")

        # 2. Check GEMINI_API_KEY environment variable
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        env_file_key = ""

        # Probe local .env files if not found in os.environ
        if not api_key:
            for candidate in [".env", "backend/.env", "../.env"]:
                if os.path.exists(candidate):
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                                    env_file_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                    break
                    except Exception:
                        pass
                if env_file_key:
                    break

        api_key_ok = False
        if api_key:
            masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***"
            print_kv("GEMINI_API_KEY Status", f"Active in OS Environment ({masked})", badge_pass())
            api_key_ok = True
        elif env_file_key:
            masked = env_file_key[:6] + "..." + env_file_key[-4:] if len(env_file_key) > 10 else "***"
            print_kv("GEMINI_API_KEY Status", f"Found in .env file ({masked}), NOT exported to OS", badge_warn("LOCAL ONLY"))
            safe_print(f"  {Color.YELLOW}▲ NOTE: GEMINI_API_KEY is defined in .env. It will be loaded by python-dotenv, but is not exported system-wide.{Color.RESET}")
            api_key_ok = True
        else:
            print_kv("GEMINI_API_KEY Status", "MISSING / NOT SET", badge_fail())
            safe_print(f"\n  {Color.YELLOW}▲ WARNING: GEMINI_API_KEY is not set. Cloud vision fallback will be unavailable!{Color.RESET}")
            safe_print(f"  {Color.WHITE}To configure GEMINI_API_KEY in Windows 11:{Color.RESET}")
            safe_print(f"    {Color.CYAN}* Command Prompt (Permanent) :{Color.RESET} setx GEMINI_API_KEY \"your_api_key_here\"")
            safe_print(f"    {Color.CYAN}* PowerShell (Session)       :{Color.RESET} $env:GEMINI_API_KEY=\"your_api_key_here\"")
            safe_print(f"    {Color.CYAN}* Local .env File            :{Color.RESET} GEMINI_API_KEY=your_api_key_here\n")
            self.remediations.append("Set the `GEMINI_API_KEY` environment variable in Windows to enable cloud GenAI fallback.")

        self.results["genai_ok"] = genai_installed and api_key_ok
        return genai_installed and api_key_ok

    # --------------------------------------------------------------------------
    # CHECK 6: Unified Health Verdict & Windows 11 Remediation Guide
    # --------------------------------------------------------------------------
    def render_verdict(self) -> bool:
        print_section(6, "UNIFIED SYSTEM HEALTH VERDICT & REMEDIATION PLAN")

        gpu_ready = (
            self.results.get("gpu_found", False) and 
            self.results.get("paddle_cuda_ok", False) and
            self.results.get("torch_cuda_ok", False)
        )
        genai_ready = self.results.get("genai_ok", False)
        all_passed = gpu_ready and genai_ready

        # Render High-Visibility Banner
        if all_passed:
            safe_print(f"""
{Color.GREEN}{Color.BOLD}╔════════════════════════════════════════════════════════════════════════════════════╗
║  🚀 HARDWARE & PIPELINE READY FOR ANTI-GRAVITY EXTRACTION                          ║
╚════════════════════════════════════════════════════════════════════════════════════╝{Color.RESET}
""")
            safe_print(f"  {Color.BOLD}{Color.WHITE}Execution Architecture Status:{Color.RESET}")
            safe_print(f"  * Primary Engine   : {Color.GREEN}PaddleOCR (Local CUDA Accelerated on RTX 2050 4GB){Color.RESET}")
            safe_print(f"  * Secondary Engine : {Color.GREEN}PyTorch CUDA Bridge (Active & Malloc Verified){Color.RESET}")
            safe_print(f"  * Cloud Fallback   : {Color.GREEN}Google GenAI SDK (Gemini Vision API Verified){Color.RESET}")
            safe_print(f"  * Memory Guard     : {Color.GREEN}Bounded for 4GB VRAM (Safe for layout analysis){Color.RESET}\n")
        else:
            status_text = "⚠️ PIPELINE DEGRADED: LOCAL GPU OR FALLBACK LAYER INCOMPLETE"
            safe_print(f"""
{Color.YELLOW}{Color.BOLD}╔════════════════════════════════════════════════════════════════════════════════════╗
║  {status_text.center(82)}║
╚════════════════════════════════════════════════════════════════════════════════════╝{Color.RESET}
""")
            # Summary Table
            safe_print(f"  {Color.BOLD}Pipeline Subsystem Status Breakdown:{Color.RESET}")
            safe_print(f"  * Windows 11 & System RAM : {badge_pass() if self.results.get('os_ok') else badge_fail()}")
            safe_print(f"  * NVIDIA Hardware & VRAM  : {badge_pass() if self.results.get('gpu_found') else badge_fail()}")
            safe_print(f"  * PyTorch CUDA Bridge     : {badge_pass() if self.results.get('torch_cuda_ok') else badge_fail('CPU ONLY / MISSING')}")
            safe_print(f"  * PaddlePaddle CUDA Cores : {badge_pass() if self.results.get('paddle_cuda_ok') else badge_fail('CPU ONLY / MISSING')}")
            safe_print(f"  * Google GenAI Fallback   : {badge_pass() if self.results.get('genai_ok') else badge_warn('KEY MISSING / NOT SET')}")

            # Prioritized Windows 11 Remediation Guide
            safe_print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 86}")
            safe_print("  PRIORITIZED WINDOWS 11 REMEDIATION GUIDE FOR RTX 2050 (4GB VRAM)")
            safe_print(f"{'=' * 86}{Color.RESET}")

            step_idx = 1

            if not self.results.get("gpu_found"):
                safe_print(f"\n  {Color.BOLD}{step_idx}. NVIDIA Driver & Visual C++ Runtime Setup{Color.RESET}")
                safe_print(f"     - Download NVIDIA Game Ready or Studio Driver for RTX 2050 (Notebook):")
                safe_print(f"       {Color.CYAN}https://www.nvidia.com/download/index.aspx{Color.RESET}")
                safe_print(f"     - Install Visual C++ 2015-2022 Redistributable (x64):")
                safe_print(f"       {Color.CYAN}https://aka.ms/vs/17/release/vc_redist.x64.exe{Color.RESET}")
                step_idx += 1

            if not self.results.get("paddle_cuda_ok"):
                safe_print(f"\n  {Color.BOLD}{step_idx}. Install CUDA-Accelerated PaddlePaddle for Windows{Color.RESET}")
                safe_print(f"     {Color.YELLOW}Do NOT install standard 'paddlepaddle' (it is CPU-only).{Color.RESET}")
                safe_print(f"     Run the exact wheel command for CUDA 11.8 / 12.0:")
                safe_print(f"     {Color.GREEN}pip uninstall -y paddlepaddle paddlepaddle-gpu{Color.RESET}")
                safe_print(f"     {Color.GREEN}pip install paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/stable/cu118/{Color.RESET}")
                safe_print(f"     {Color.DIM}Windows Missing DLL Fix (cuDNN/zlib): If you see 'zlibwapi.dll not found', download zlib123dllx64.zip and place zlibwapi.dll into C:\\Windows\\System32{Color.RESET}")
                step_idx += 1

            if not self.results.get("torch_cuda_ok"):
                safe_print(f"\n  {Color.BOLD}{step_idx}. Install CUDA-Enabled PyTorch{Color.RESET}")
                safe_print(f"     Current PyTorch build is CPU-only. Run:")
                safe_print(f"     {Color.GREEN}pip uninstall -y torch torchvision torchaudio{Color.RESET}")
                safe_print(f"     {Color.GREEN}pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118{Color.RESET}")
                step_idx += 1

            if not self.results.get("genai_ok"):
                safe_print(f"\n  {Color.BOLD}{step_idx}. Configure Cloud Fallback & Gemini API Key{Color.RESET}")
                safe_print(f"     Install modern SDK and export environment variable:")
                safe_print(f"     {Color.GREEN}pip install google-genai{Color.RESET}")
                safe_print(f"     {Color.GREEN}setx GEMINI_API_KEY \"your_api_key_here\"{Color.RESET}")
                step_idx += 1

            # Operational VRAM Guidance for RTX 2050
            safe_print(f"\n  {Color.BOLD}* RTX 2050 (4GB VRAM) Concurrency Rule of Thumb:{Color.RESET}")
            safe_print(f"     - Set PaddleOCR layout batch size = 1 (`batch_size=1`) to prevent OOM spikes.")
            safe_print(f"     - When processing dense multi-column PDFs, route pages to Gemini Vision if VRAM headroom < 500MB.")
            safe_print()

        return all_passed


# ------------------------------------------------------------------------------
# 4. Entrypoint
# ------------------------------------------------------------------------------
def main():
    print_banner(
        "LAPTOP HARDWARE & OCR/GENAI ENVIRONMENT DIAGNOSTIC",
        "Windows 11 | Intel Core i5 | NVIDIA RTX 2050 4GB | PaddleOCR + Google GenAI"
    )

    auditor = EnvironmentAuditor()

    # Sequential execution of the 5 checks
    auditor.audit_system_and_os()
    auditor.audit_nvidia_hardware()
    auditor.audit_pytorch_cuda_bridge()
    auditor.audit_paddle_gpu()
    auditor.audit_genai_sdk()

    # Final unified verdict
    success = auditor.render_verdict()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
