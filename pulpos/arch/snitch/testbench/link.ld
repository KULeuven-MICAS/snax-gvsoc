
OUTPUT_ARCH(riscv)
ENTRY( _start )
MEMORY
{
  /* 0x8000 are reserved at the end of the mem for the boot rom */
  mem           : ORIGIN = @mem_start@, LENGTH = @mem_size@
}

/*
 * This linker script try to put FC data in mem private bank0 and FC code
 * in mem private bank1 to avoid contention between FC code and data
 * as FC has no instruction cache and is so often accessing mem to
 * get instructions. Everything can be shifted in case one bank is full.
 *
 * Cluster code and initialized data are put in shared banks to not polute
 * private banks which are quite small, and also avoid contentions between
 * cluster cache refill and FC.
 */


SECTIONS
{
  .init :
  {
    . = ALIGN(8);
    KEEP( *(.init) )
    . = ALIGN(8);
  } > mem


  .fini :
  {
    . = ALIGN(8);
    KEEP( *(.fini) )
    . = ALIGN(8);
  } > mem


  .preinit_array : {
    . = ALIGN(8);
    PROVIDE_HIDDEN (__preinit_array_start = .);
    KEEP (*(.preinit_array))
    PROVIDE_HIDDEN (__preinit_array_end = .);
    . = ALIGN(8);
  } > mem


  .init_array : {
    . = ALIGN(8);
    PROVIDE_HIDDEN (__init_array_start = .);
    __CTOR_LIST__ = .;
    LONG((__CTOR_END__ - __CTOR_LIST__) / 4 - 2)
    KEEP(*(.ctors.start))
    KEEP(*(.ctors))
    KEEP (*(SORT(.init_array.*)))
    KEEP (*(.init_array ))
    LONG(0)
    __CTOR_END__ = .;
    PROVIDE_HIDDEN (__init_array_end = .);
    . = ALIGN(8);
  } > mem


  .fini_array : {
    . = ALIGN(8);
    PROVIDE_HIDDEN (__fini_array_start = .);
    __DTOR_LIST__ = .;
    LONG((__DTOR_END__ - __DTOR_LIST__) / 4 - 2)
    KEEP(*(.dtors.start))
    KEEP(*(.dtors))
    LONG(0)
    __DTOR_END__ = .;
    KEEP (*(SORT(.fini_array.*)))
    KEEP (*(.fini_array ))
    PROVIDE_HIDDEN (__fini_array_end = .);
    . = ALIGN(8);
  } > mem


  .boot : {
    . = ALIGN(8);
    *(.boot)
    *(.boot.data)
    . = ALIGN(8);
  } > mem


  .rodata : {
    . = ALIGN(8);
    *(.rodata);
    *(.rodata.*)
    *(.srodata);
    *(.srodata.*)
    *(.eh_frame*)
    *(.gnu.linkonce.r.*)
    . = ALIGN(8);
  } > mem


  .got : {
    . = ALIGN(8);
    *(.got.plt) * (.igot.plt) *(.got) *(.igot)
    . = ALIGN(8);
  } > mem


  .shbss : {
    . = ALIGN(8);
    *(.shbss)
    . = ALIGN(8);
  } > mem


  .talias : {
  } > mem


  .gnu.offload_funcs : {
    . = ALIGN(8);
    KEEP(*(.gnu.offload_funcs))
    . = ALIGN(8);
  } > mem


  .gnu.offload_vars : {
    . = ALIGN(8);
    KEEP(*(.gnu.offload_vars))
    . = ALIGN(8);
  } > mem


  .stack : {
    . = ALIGN(8);
    . = ALIGN(16);
    stack_start = .;
    . = . + 0x800;
    stack = .;
    . = ALIGN(8);
  } > mem


  .data : {
    . = ALIGN(8);
    sdata  =  .;
    _sdata  =  .;
    *(.data_fc)
    *(.data_fc.*)
    *(.data);
    *(.data.*)
    *(.sdata);
    *(.sdata.*)
    *(.heapmemram)
    *(.fcTcdm)
    *(.fcTcdm.*)
    *(.fcTcdm_g)
    *(.fcTcdm_g.*)
    . = ALIGN(8);
    edata  =  .;
    _edata  =  .;
  } > mem


  .bss : {
    . = ALIGN(8);
    _bss_start = .;
    *(.bss)
    *(.bss.*)
    *(.sbss)
    *(.sbss.*)
    *(COMMON)
    . = ALIGN(8);
    _bss_end = .;
  } > mem


  .vectors MAX(0x1c010000,ALIGN(256)) :
  {
    __pi_irq_vector_base = .;
    KEEP(*(.vectors))
    . = . + 0x80;
    __pi_fast_irq_vector_base = .;
    KEEP(*(.fast_vectors))
    . = . + 0x80;
    __irq_cluster_vector_base__ = .;
    KEEP(*(.cluster_vectors))
    . = ALIGN(8);
  } > mem

  .text :
  {
    . = ALIGN(16);
    _stext = .;
    *(.text)
    *(.text.*)
    *(.gnu.linkonce.t.*)
    *(.text_static)
    *(.text_static.*)
    _etext  =  .;
    *(.lit)
    *(.shdata)
    __cluster_text_start = .;
    *(.cluster.text)
    *(.cluster.text.*)
    /* This alignment is needed on RTL platforms to avoid getting X in the code */
    . = ALIGN(16);
    _endtext = .;
    __cluster_text_end = .;
    /* This alignment is needed on RTL platforms to avoid getting X in the code */
    . = ALIGN(16);
  } > mem

}
