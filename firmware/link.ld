OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
  ROM (rx) : ORIGIN = 0x80000000, LENGTH = 4K
  RAM (rw) : ORIGIN = 0x80010000, LENGTH = 1K
}
SECTIONS {
  .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } > ROM
  .data : ALIGN(4) { _data_start = .; *(.data*) *(.sdata*) . = ALIGN(4); _data_end = .; } > RAM AT>ROM
  _data_load = LOADADDR(.data);
  .bss (NOLOAD) : ALIGN(4) { _bss_start = .; *(.bss*) *(.sbss*) *(COMMON) . = ALIGN(4); _bss_end = .; } > RAM
  _stack_top = ORIGIN(RAM) + LENGTH(RAM);
  ASSERT(_bss_end <= _stack_top - 512, "Need at least 512 bytes stack")
  /DISCARD/ : { *(.comment) *(.eh_frame*) }
}
