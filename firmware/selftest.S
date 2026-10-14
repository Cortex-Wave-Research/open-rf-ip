.option norvc
.option norelax
.text
.globl cpu_selftest
cpu_selftest:
    addi sp, sp, -16
    sw ra, 12(sp)
    li t0, 37
    li t1, 19
    add t2, t0, t1
    li t3, 56
    bne t2, t3, fail
    sub t2, t0, t1
    li t3, 18
    bne t2, t3, fail
    and t2, t0, t1
    li t3, 1
    bne t2, t3, fail
    or t2, t0, t1
    li t3, 55
    bne t2, t3, fail
    xor t2, t0, t1
    li t3, 54
    bne t2, t3, fail
    li t1, 3
    sll t2, t0, t1
    li t3, 296
    bne t2, t3, fail
    srl t2, t2, t1
    bne t2, t0, fail
    li t0, -32
    sra t2, t0, t1
    li t3, -4
    bne t2, t3, fail
    slt t2, t0, t1
    li t3, 1
    bne t2, t3, fail
    sltu t2, t0, t1
    bne t2, zero, fail
    blt t1, t0, fail
    bge t0, t1, fail
    bltu t0, t1, fail
    bgeu t1, t0, fail
    li t0, 0x12345678
    sw t0, 0(sp)
    lw t1, 0(sp)
    bne t0, t1, fail
    li t0, 0x80
    sb t0, 1(sp)
    lbu t1, 1(sp)
    bne t0, t1, fail
    lb t1, 1(sp)
    li t2, -128
    bne t1, t2, fail
    li t0, 0x8123
    sh t0, 2(sp)
    lhu t1, 2(sp)
    bne t0, t1, fail
    lh t1, 2(sp)
    li t2, -32477
    bne t1, t2, fail
    lw t1, 0(sp)
    li t2, 0x81238078
    bne t1, t2, fail
    jal ra, function
    li t0, 43
    bne a0, t0, fail
    la t0, function
    jalr ra, t0, 0
    li t0, 43
    bne a0, t0, fail
    li a0, 0
    j finish
function:
    li a0, 42
    addi a0, a0, 1
    ret
fail:
    li a0, 1
finish:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret
