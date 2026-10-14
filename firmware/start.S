.option norvc
.option norelax
.section .text.start,"ax",@progbits
.globl _start
_start:
    li t0, 0x80010000
    li t1, 0x80010400
1:  sw zero, 0(t0)
    addi t0, t0, 4
    bltu t0, t1, 1b
    la t0, _data_load
    la t1, _data_start
    la t2, _data_end
2:  bgeu t1, t2, 3f
    lw t3, 0(t0)
    sw t3, 0(t1)
    addi t0, t0, 4
    addi t1, t1, 4
    j 2b
3:  # Deterministic bare-metal C entry: no incoming arguments, TLS, or gp use.
    # Clear all other writable GPRs after the data-copy temporaries are finished.
    # The final stack setup and call below establish sp and ra respectively.
    # This is software policy, not an assumption about CPU power-up register bits.
    addi x3, x0, 0
    addi x4, x0, 0
    addi x5, x0, 0
    addi x6, x0, 0
    addi x7, x0, 0
    addi x8, x0, 0
    addi x9, x0, 0
    addi x10, x0, 0
    addi x11, x0, 0
    addi x12, x0, 0
    addi x13, x0, 0
    addi x14, x0, 0
    addi x15, x0, 0
    addi x16, x0, 0
    addi x17, x0, 0
    addi x18, x0, 0
    addi x19, x0, 0
    addi x20, x0, 0
    addi x21, x0, 0
    addi x22, x0, 0
    addi x23, x0, 0
    addi x24, x0, 0
    addi x25, x0, 0
    addi x26, x0, 0
    addi x27, x0, 0
    addi x28, x0, 0
    addi x29, x0, 0
    addi x30, x0, 0
    addi x31, x0, 0
    la sp, _stack_top
    call main
    li t0, 0x40010000
    li t1, 0xdeadffff
    sw t1, 0(t0)
4:  j 4b
