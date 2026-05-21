#define _GNU_SOURCE

#include <seccomp.h>

#include <stdio.h>
#include <stdlib.h>

#include <unistd.h>

#include "sandbox_seccomp.h"

#define DENY(syscall)                                      \
    do {                                                   \
        if(seccomp_rule_add(                               \
            ctx,                                           \
            SCMP_ACT_KILL_PROCESS,                         \
            SCMP_SYS(syscall),                             \
            0                                              \
        ) < 0){                                            \
            perror("seccomp_rule_add");                    \
            seccomp_release(ctx);                          \
            exit(1);                                       \
        }                                                  \
    } while(0)

void setup_seccomp(void){

    scmp_filter_ctx ctx;

    // =====================================
    // Docker-like blacklist mode
    // Default action: ALLOW
    // =====================================

    ctx = seccomp_init(SCMP_ACT_ALLOW);

    if(ctx == NULL){
        perror("seccomp_init");
        exit(1);
    }

    // =====================================
    // Namespace / mount escape
    // =====================================

    DENY(mount);
    DENY(umount2);
    DENY(pivot_root);
    DENY(setns);
    DENY(unshare);

    // =====================================
    // Kernel module operations
    // =====================================

    DENY(init_module);
    DENY(finit_module);
    DENY(delete_module);

    // =====================================
    // Process inspection
    // =====================================

    DENY(ptrace);
    DENY(process_vm_readv);
    DENY(process_vm_writev);
    DENY(kcmp);

    // =====================================
    // Dangerous file handle operations
    // =====================================

    DENY(open_by_handle_at);
    DENY(name_to_handle_at);

    // =====================================
    // io_uring
    // =====================================

    DENY(io_uring_setup);
    DENY(io_uring_enter);
    DENY(io_uring_register);

    // =====================================
    // BPF / perf
    // =====================================

    DENY(bpf);
    DENY(perf_event_open);

    // =====================================
    // Kernel keyring
    // =====================================

    DENY(add_key);
    DENY(keyctl);
    DENY(request_key);

    // =====================================
    // Reboot / swap
    // =====================================

    DENY(reboot);
    DENY(swapon);
    DENY(swapoff);

    // =====================================
    // Time modification
    // =====================================

    DENY(clock_settime);
    DENY(settimeofday);
    DENY(stime);

    // =====================================
    // Kernel loading
    // =====================================

    DENY(kexec_load);

    // =====================================
    // Memory policy
    // =====================================

    DENY(set_mempolicy);
    DENY(mbind);
    DENY(move_pages);

    // =====================================
    // Legacy / obsolete
    // =====================================

    DENY(_sysctl);
    DENY(sysfs);
    DENY(uselib);
    DENY(ustat);
    DENY(vm86);
    DENY(vm86old);

    // =====================================
    // userfaultfd
    // =====================================

    DENY(userfaultfd);

    // =====================================
    // personality
    // =====================================

    DENY(personality);

    // =====================================
    // Load seccomp filter
    // =====================================

    if(seccomp_load(ctx) < 0){
        perror("seccomp_load");
        seccomp_release(ctx);
        exit(1);
    }

    seccomp_release(ctx);

    printf(
        "[Sandbox] Docker-like seccomp blacklist enabled\n"
    );
}