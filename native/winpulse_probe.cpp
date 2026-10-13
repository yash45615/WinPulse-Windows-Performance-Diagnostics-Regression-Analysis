
#define NOMINMAX
#include <windows.h>
#include <psapi.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>

#pragma comment(lib, "Psapi.lib")

static std::string utc_timestamp() {
    SYSTEMTIME st{};
    GetSystemTime(&st);

    char buffer[40]{};
    std::snprintf(
        buffer, sizeof(buffer),
        "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ",
        st.wYear, st.wMonth, st.wDay,
        st.wHour, st.wMinute, st.wSecond, st.wMilliseconds
    );
    return buffer;
}

static bool read_cpu_times(
    ULONGLONG& idle,
    ULONGLONG& kernel,
    ULONGLONG& user
) {
    FILETIME idle_ft{}, kernel_ft{}, user_ft{};
    if (!GetSystemTimes(&idle_ft, &kernel_ft, &user_ft)) {
        return false;
    }

    auto to_u64 = [](const FILETIME& ft) -> ULONGLONG {
        ULARGE_INTEGER value{};
        value.LowPart = ft.dwLowDateTime;
        value.HighPart = ft.dwHighDateTime;
        return value.QuadPart;
    };

    idle = to_u64(idle_ft);
    kernel = to_u64(kernel_ft);
    user = to_u64(user_ft);
    return true;
}

static double cpu_usage(
    ULONGLONG old_idle, ULONGLONG old_kernel, ULONGLONG old_user,
    ULONGLONG new_idle, ULONGLONG new_kernel, ULONGLONG new_user
) {
    const auto idle_delta = new_idle - old_idle;
    const auto total_delta =
        (new_kernel - old_kernel) + (new_user - old_user);

    if (total_delta == 0 || idle_delta > total_delta) {
        return 0.0;
    }

    const double percent =
        100.0 * static_cast<double>(total_delta - idle_delta)
        / static_cast<double>(total_delta);

    return std::clamp(percent, 0.0, 100.0);
}

int main(int argc, char* argv[]) {
    int samples = 10;
    int interval_seconds = 1;
    std::string output_path = "native_probe.jsonl";

    if (argc > 1) samples = std::atoi(argv[1]);
    if (argc > 2) interval_seconds = std::atoi(argv[2]);
    if (argc > 3) output_path = argv[3];

    if (samples < 1 || samples > 300 ||
        interval_seconds < 1 || interval_seconds > 60) {
        std::cerr
            << "Usage: winpulse_probe.exe [samples:1-300] "
            << "[interval_seconds:1-60] [output.jsonl]\n";
        return 2;
    }

    std::ofstream out(output_path, std::ios::out | std::ios::app);
    if (!out) {
        std::cerr << "Cannot open output file: " << output_path << "\n";
        return 3;
    }

    ULONGLONG old_idle{}, old_kernel{}, old_user{};
    if (!read_cpu_times(old_idle, old_kernel, old_user)) {
        std::cerr << "GetSystemTimes failed: " << GetLastError() << "\n";
        return 4;
    }

    std::cout << "WinPulse Native Probe\n"
              << "Samples: " << samples
              << ", interval: " << interval_seconds << " second(s)\n"
              << "Output: " << output_path << "\n";

    for (int i = 0; i < samples; ++i) {
        std::this_thread::sleep_for(
            std::chrono::seconds(interval_seconds)
        );

        ULONGLONG new_idle{}, new_kernel{}, new_user{};
        if (!read_cpu_times(new_idle, new_kernel, new_user)) {
            std::cerr << "GetSystemTimes failed: "
                      << GetLastError() << "\n";
            return 4;
        }

        const double cpu = cpu_usage(
            old_idle, old_kernel, old_user,
            new_idle, new_kernel, new_user
        );

        old_idle = new_idle;
        old_kernel = new_kernel;
        old_user = new_user;

        MEMORYSTATUSEX memory{};
        memory.dwLength = sizeof(memory);
        if (!GlobalMemoryStatusEx(&memory)) {
            std::cerr << "GlobalMemoryStatusEx failed: "
                      << GetLastError() << "\n";
            return 5;
        }

        PROCESS_MEMORY_COUNTERS_EX process_memory{};
        process_memory.cb = sizeof(process_memory);

        const bool process_ok = GetProcessMemoryInfo(
            GetCurrentProcess(),
            reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&process_memory),
            sizeof(process_memory)
        ) != 0;

        std::ostringstream row;
        row << std::fixed << std::setprecision(2)
            << "{\"timestamp\":\"" << utc_timestamp() << "\""
            << ",\"pid\":" << GetCurrentProcessId()
            << ",\"process_name\":\"winpulse_probe.exe\""
            << ",\"system_cpu_percent\":" << cpu
            << ",\"memory_total_bytes\":" << memory.ullTotalPhys
            << ",\"memory_available_bytes\":" << memory.ullAvailPhys
            << ",\"memory_load_percent\":" << memory.dwMemoryLoad;

        if (process_ok) {
            row << ",\"process_working_set_bytes\":"
                << process_memory.WorkingSetSize;
        } else {
            row << ",\"process_working_set_bytes\":null";
        }

        row << "}";
        out << row.str() << '\n';
        out.flush();

        if (!out) {
            std::cerr << "Failed to write output record.\n";
            return 6;
        }

        std::cout << row.str() << '\n';
    }

    std::cout << "Capture completed successfully.\n";
    return 0;
}
