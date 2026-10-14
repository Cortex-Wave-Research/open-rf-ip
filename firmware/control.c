#include "openrf.h"

typedef unsigned int u32;
static volatile u32 *const csr = (volatile u32 *)OPENRF_BASE;
static volatile u32 *const mailbox = (volatile u32 *)MAILBOX_BASE;
extern u32 cpu_selftest(void);
static u32 rd(u32 offset) { return csr[offset >> 2]; }
static void wr(u32 offset, u32 value) { csr[offset >> 2] = value; }
static void command(u32 value) { wr(ADDR_COMMAND, value); }
__attribute__((noreturn)) static void fail(u32 code) {
    *mailbox = 0xdead0000u | code;
    for (;;) __asm__ volatile("j .");
}
static void require(u32 condition, u32 code) { if (!condition) fail(code); }
__attribute__((noinline)) static void delay(u32 count) {
    for (volatile u32 n = 0; n < count; ++n) __asm__ volatile("" ::: "memory");
}
static void pair(u32 offset, u32 lo, u32 hi) {
    wr(offset, lo); wr(offset + 4, hi);
}
int main(void) {
    require(cpu_selftest() == 0, 1);
    *mailbox = 0x10;
    require(rd(ADDR_IP_ID) == IP_ID_VALUE, 2);
    require(rd(ADDR_ABI_VERSION) == ABI_VERSION_VALUE, 3);
    u32 caps = rd(ADDR_CAPABILITIES);
    u32 hp = !!(caps & CAP_HIGH_PURITY);
    u32 chirp = !!(caps & CAP_CHIRP);
    require(caps == ((hp ? CAP_HIGH_PURITY : CAP_COMPACT) | CAP_PAUSE |
                    (chirp ? CAP_CHIRP | CAP_REPEAT : CAP_TONE)), 4);
    wr(ADDR_SCRATCH, 0x81234567);
    require(rd(ADDR_SCRATCH) == 0x81234567, 5);
    require(rd(ADDR_STATUS) == 0 && rd(ADDR_ERROR_STATUS) == 0, 6);
    *mailbox = 0x20;

    command(CMD_START);
    require(rd(ADDR_ERROR_STATUS) & ERR_START_WITHOUT_VALID_CONFIG, 7);
    command(CMD_CLEAR_STATUS);
    wr(ADDR_MODE, chirp ? MODE_CHIRP : MODE_TONE);
    // LOW-only, HIGH-only and paired writes are independently observed by the
    // testbench at the unchanged CSR active outputs, without firmware backdoors.
    wr(ADDR_NCO_PHASE_INC_LO, 17);
    require(rd(ADDR_CONFIG_SEQUENCE) == 0, 8);
    wr(ADDR_CHIRP_START_HI, hp ? 0x051eb851 : 0);
    require(rd(ADDR_CONFIG_SEQUENCE) == 0, 9);
    pair(ADDR_NCO_PHASE_INC_LO, hp ? 0x99999999 : 0x19999999,
         hp ? 0x19999999 : 0);
    pair(ADDR_CHIRP_START_LO, hp ? 0xeb851eb8 : 0x051eb852,
         hp ? 0x051eb851 : 0);
    pair(ADDR_CHIRP_STEP_LO, hp ? 0x048cc0f3 : 77317,
         hp ? 0x00012e05 : 0);
    wr(ADDR_CHIRP_LENGTH, 10000);
    wr(ADDR_CHIRP_CONFIG, 0);
    require(rd(ADDR_CONFIG_SEQUENCE) == 0, 10);
    command(CMD_COMMIT);
    require(rd(ADDR_CONFIG_SEQUENCE) == 1, 11);
    require((rd(ADDR_STATUS) & (STATUS_CONFIG_VALID | STATUS_CONFIG_DIRTY)) ==
            STATUS_CONFIG_VALID, 12);
    // Rejected whole-bank commit, including compact high/sign-extension rules.
    wr(ADDR_CHIRP_CONFIG, 2);
    command(CMD_COMMIT);
    require(rd(ADDR_CONFIG_SEQUENCE) == 1, 13);
    require(rd(ADDR_ERROR_STATUS) & ERR_INVALID_CONFIGURATION, 14);
    wr(ADDR_CHIRP_CONFIG, 0);
    if (!hp) {
        wr(ADDR_NCO_PHASE_INC_HI, 1); command(CMD_COMMIT);
        require(rd(ADDR_CONFIG_SEQUENCE) == 1, 15);
        wr(ADDR_NCO_PHASE_INC_HI, 0);
        wr(ADDR_CHIRP_STEP_HI, 0xffffffff); command(CMD_COMMIT);
        require(rd(ADDR_CONFIG_SEQUENCE) == 1, 16);
        wr(ADDR_CHIRP_STEP_HI, 0);
    }
    command(CMD_COMMIT);
    require(rd(ADDR_CONFIG_SEQUENCE) == 2, 17);
    command(CMD_CLEAR_STATUS);
    *mailbox = 0x30;
    wr(ADDR_RUN_CONTROL, RUN_ENABLE);
    if (chirp) command(CMD_START);
    require(rd(ADDR_STATUS) & STATUS_BUSY, 18);
    command(CMD_COMMIT);
    require(rd(ADDR_ERROR_STATUS) & ERR_COMMIT_WHILE_BUSY, 19);
    require(rd(ADDR_CONFIG_SEQUENCE) == 2, 20);
    if (!chirp) {
        command(CMD_START);
        require(rd(ADDR_ERROR_STATUS) & ERR_BAD_COMMAND, 21);
        require(rd(ADDR_CONFIG_SEQUENCE) == 2, 22);
    }
    delay(8);
    wr(ADDR_RUN_CONTROL, 0);
    *mailbox = 0x40;
    delay(23);
    wr(ADDR_RUN_CONTROL, RUN_ENABLE);
    *mailbox = 0x50;
    if (chirp) {
        u32 limit = 10000;
        while (rd(ADDR_STATUS) & STATUS_BUSY) if (--limit == 0) fail(23);
        require(rd(ADDR_STATUS) & STATUS_DONE_STICKY, 24);
    } else {
        delay(1600);
    }
    wr(ADDR_RUN_CONTROL, 0);
    *mailbox = 0x60;
    command(CMD_CLEAR_STATUS);
    require(rd(ADDR_ERROR_STATUS) == 0, 25);
    require(mailbox[1] == 0, 26);
    // Unmapped CSR and misaligned CSR reads cannot trap; check both the frozen
    // CSR error and the separate integration sticky fault. Inline LW guarantees
    // the misalignment test is one CPU instruction, not C undefined behavior.
    (void)rd(0x80);
    require(rd(ADDR_ERROR_STATUS) & ERR_ILLEGAL_BUS_ACCESS, 27);
    require(mailbox[1] == 1, 28);
    command(CMD_CLEAR_STATUS);
    u32 ignored;
    __asm__ volatile("lw %0, 1(%1)" : "=r"(ignored) : "r"(OPENRF_BASE));
    require(rd(ADDR_ERROR_STATUS) & ERR_ILLEGAL_BUS_ACCESS, 29);
    require(rd(ADDR_CONFIG_SEQUENCE) == 2, 30);
    command(CMD_CLEAR_STATUS);
    *mailbox = 0x600d600d;
    for (;;) __asm__ volatile("j .");
}
