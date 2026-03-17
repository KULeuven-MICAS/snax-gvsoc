# XIP

## Description

This IP allows to execute code or fetch data from any udma flash/ram. Instruction and data are
then mapped in a virtual memory area starting @ 0x20000000 and ending @ 0x2FFFFFFF.

## Registers

| Register Name        | Offset | Size | Register Type | Host Access Type | Block Access Type | Default    | Properties                 | Description                                                                                                                      |
|:---------------------|:-------|:-----|---------------|------------------|-------------------|------------|----------------------------|:---------------------------------------------------------------------------------------------------------------------------------|
| CFG_XIP              | 0x0    | 32   | Config        | R/W              | R                 | 0x0        |                            | Main config register for XIP (tlb mode)                                                                                          |
| CFG_SOFT_RESET       | 0x4    | 32   | Config        | R/W              | R/W               | 0x0        |                            | Flush mask register for pages, allow keeping page synced with EXT                                                                |
| CLUSTER_ERR_PAGE     | 0x8    | 32   | Config        | R/W              | W                 | 0x20000000 |                            | page address for first detected cluster error                                                                                    |
| ERR_PAGE             | 0xC    | 32   | Config        | R/W              | W                 | 0x20000000 |                            | page address for first detected FC insn error + one hot for if/where ro violation                                                |
| CFG_VIRT_ADDR0       | 0x10   | 32   | Config        | R/W              | R                 | 0x20000000 | template=CFG_VIRT_ADDR     | Base virtual address for hyper0                                                                                                  |
| CFG_VIRT_ADDR1       | 0x14   | 32   | Config        | R/W              | R                 | 0x20000000 | template=CFG_VIRT_ADDR     | Base virtual address for hyper1                                                                                                  |
| CFG_VIRT_ADDR2       | 0x18   | 32   | Config        | R/W              | R                 | 0x20000000 | template=CFG_VIRT_ADDR     | Base virtual address for mram                                                                                                    |
| CFG_EXT_ADDR0        | 0x1C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_EXT_ADDR      | Base external address for hyper0                                                                                                 |
| CFG_EXT_ADDR1        | 0x20   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_EXT_ADDR      | Base external address for hyper1                                                                                                 |
| CFG_EXT_ADDR2        | 0x24   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_EXT_ADDR      | Base external address for mram                                                                                                   |
| CFG_MNT_SIZE0        | 0x28   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_MNT_SIZE      | Virt memory size for hyper0 (pages)                                                                                              |
| CFG_MNT_SIZE1        | 0x2C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_MNT_SIZE      | Virt memory size for hyper1 (pages)                                                                                              |
| CFG_MNT_SIZE2        | 0x30   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_MNT_SIZE      | Virt memory size for mram   (pages)                                                                                              |
| CFG_PAGE_SIZE0       | 0x34   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE_SIZE     | Page size for hyper0 (512B - 64KB, power of two)                                                                                 |
| CFG_PAGE_SIZE1       | 0x38   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE_SIZE     | Page size for hyper1 (512B - 64KB, power of two)                                                                                 |
| CFG_PAGE_SIZE2       | 0x3C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE_SIZE     | Page size for mram (512B - 64KB, power of two)                                                                                   |
| CFG_PAGE0            | 0x40   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page0 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE1            | 0x44   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page1 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE2            | 0x48   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page2 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE3            | 0x4C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page3 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE4            | 0x50   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page4 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE5            | 0x54   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page5 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE6            | 0x58   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page6 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE7            | 0x5C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page7 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE8            | 0x60   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page8 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE9            | 0x64   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page9 configuration  (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE10           | 0x68   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page10 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE11           | 0x6C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page11 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE12           | 0x70   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page12 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE13           | 0x74   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page13 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE14           | 0x78   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page14 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_PAGE15           | 0x7C   | 32   | Config        | R/W              | R                 | 0x0        | template=CFG_PAGE          | page15 configuration (bit [31:30]: device id, [29]: active bit, [21:0]: l2 offset)                                               |
| CFG_TLB_VIRT_PAGE_0  | 0x80   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_1  | 0x84   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_2  | 0x88   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_3  | 0x8C   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_4  | 0x90   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_5  | 0x94   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_6  | 0x98   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_7  | 0x9C   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_8  | 0xA0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_9  | 0xA4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_10 | 0xA8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_11 | 0xAC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_12 | 0xB0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_13 | 0xB4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_14 | 0xB8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_VIRT_PAGE_15 | 0xBC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_VIRT_PAGE | TLB virtual page configuration (bit [31:8]: virtual address, [6:4]: page size, [3:2] page_id, [1]: reserved, [0] page_cacheable) |
| CFG_TLB_PHYS_PAGE_0  | 0xC0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_1  | 0xC4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_2  | 0xC8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_3  | 0xCC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_4  | 0xD0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_5  | 0xD4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_6  | 0xD8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_7  | 0xDC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_8  | 0xE0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_9  | 0xE4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_10 | 0xE8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_11 | 0xEC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_12 | 0xF0   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_13 | 0xF4   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_14 | 0xF8   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_TLB_PHYS_PAGE_15 | 0xFC   | 32   | Config        | R/W              | R/W               | 0x0        | template=CFG_TLB_PHYS_PAGE | TLB physical page configuration (bit [31:0]: physical address)                                                                   |
| CFG_XIP_LRU          | 0x100  | 32   | Config        | R                | R/W               | 0x0        |                            | TLB current LRU entry                                                                                                            |
| CFG_XIP_LOCK_ATTR    | 0x104  | 2    | Config        | R                | R/W               | 0x0        |                            |  add default/lock/unlock attribute to the page of the next fc data request                                         |





### CFG_XIP

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                            |
| ---------- | ------------ | ---- | ---------------- | -------------- | ----------- | -------------------------------------- |
| TLB_EN     | 0            | 1    | R/W              | R              | 0x0         | Enable or Disable TLB mode             |
| DEVICE_RO  | 1            | 3    | R/W              | R              | 0x0         | Flag to check whether device is RO     |
| POWER_ON   | 16           | 1    | R/W              | R              | 0x0         | Inform XIP that cluster is powered on  |



### CFG_SOFT_RESET

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                                                               |
| ---------- | ------------ | ---- | ---------------- | -------------- | ----------- | ------------------------------------------------------------------------- |
| RESET      | 0            | 1    | R/W              | R/W            | 0x0         | Flush dirty pages, and reset logic to enable reconfiguration. Falls to 0 when done.  |

### CFG_VIRT_ADDR

When NOT in TLB mode this register alongside CFG_MNT_SIZE and CFG_PAGE_SIZE serve to
create the virtual address boundaries for a peripheral to translate.

For example if we set this register to 0x2100_0000 and mount size to 0x1000 and page size to 0 ((512 byte page size)) 
then our boundary will be from 0x2100_0000 to 0x2120_0000 (0x2100_0000 + (0x1000 << 9)). The
virtual address has to hit inside this boundary

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                                                                                       |
| ---------  | ------------ | ---- | ---------------- | -------------- | ----------- | ------------------------------------------------------------------------------------------------- |
| VIRT_ADDR  | 0            | 32   | R/W              | R              | 0x20000000  | Start of Virtual Address for external peripheral 0 Must be in the range[0x2000_0000-0x2FFF_FFFF]  |



### CFG_EXT_ADDR

When NOT in TLB mode this register is used in case of a miss to refill data to the L2 memory from
the peripheral that the access was a miss

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                                          |
| ---------  | ------------ | ---- | ---------------- | -------------- | ----------- | ---------------------------------------------------- |
| EXT_ADDR   | 0            | 32   | R/W              | R              | 0x0         | Start of External Address for external peripheral 0  |



### CFG_MNT_SIZE

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                                                                                     |
| ---------  | ------------ | ---- | ---------------- | -------------- | ----------- | ----------------------------------------------------------------------------------------------- |
| MNT_SIZE   | 0            | 16   | R/W              | R              | 0x0         | Size of the mounted region in pages for peripheral 0 (total size of region = this reg*page size) |



### CFG_PAGE_SIZE

Possible values:
- Page sizes are represented as powers of 512B. To obtain & 512B page size, set 0, for 1KB, set 1,
for 4KB set 3 etc. Maximum page size is 64KB

- If TLB mode is enabled, PAGE_SIZE0 is used for all pages/devices

#### Fields

| Field Name    | Offset | Size | Host Access Type | Block Access Type | Default | Description                                                                                  |
| ---           | ---    | ---  | ---              | ---               | ---     | -------------------------------------------------------------------------------------------- |
| PAGE_SIZE     | 0      | 3    | R/W              | R                 | 0x0     | Size of pages for peripheral 0 0: 512Bytes 1: 1KBytes 2: 2KBytes 3: 4KBytes ...  7: 64KBytes |



### CFG_PAGE

Device ID:
- Choose to which device the page is dedicated (hyperX, mram)
- Value is between 0 & 2

Active bit:
- Set to 1 to make page "active"

L2 Offset:
- Offset compared to L2 ram base (0x1c000000)
- only bit [21:0] are used.

#### Fields

| Field Name     | Offset | Size | Host Access Type | Block Access Type | Default | Description                                                                                  |
| -------------- | ---    | ---  | ---              | ---               | ---     | -------------------------------------------------------------------------------------------- |
| INT_ADDR       |  0     | 22   | R/W              | R                 | 0x0     | 22 LSB of L2 Address of the page                                                             |
| CACHEABLE      |  28    | 1    | R/W              | R                 | 0x0     | Make icache aware of this page or not. Shared with TLB_VIRT_PAGE.CACHEABLE                                                     |
| ACTIVE         |  29    | 1    | R/W              | R                 | 0x0     | Make page "active" or "ignored"                                                              |
| PER_ID         |  30    | 2    | R/W              | R                 | 0x0     | Peripheral ID (0: Hyper0, 1: Hyper1, 2: MRAM, 3 is invalid and can't be set) Shared with TLB_VIRT_PAGE.TLB_PAGE_ID  |

### CFG_TLB_VIRT_PAGE

If TLB mode is enabled this table is used in case of a hit or miss.

- If one of the table entries matches the virtual address then we take that
  entry and use it to access the CFG_PAGE(0-15). For example, if we hit 
  CFG_TLB_VIRT_PAGE_3 then we use CFG_PAGE3 to access the L2 memory

- When a miss occurs an address is assembled using the MSB bits
  from the TLB virtual address and the LSB bits from the physical one
  depending on the page size

- This field must be written last at init (gates the function of the IP)
#### Fields

| Field Name         | Offset | Size | Host Access Type | Block Access Type | Default | Description                                                                                       |
| ------------------ | ---    | ---  | ---              | ---               | ---     | ------------------------------------------------------------------------------------------------- |
| TLB_VIRT_ADDR      |  9     | 19   | R/W              | R/W               | 0x0     | Virtual address TAG entry that is compared against the virtual address seeking for access         |                                                                        |
| TLB_VALID_DATA     |  7     | 1    | R                | R                 | 0x0     | When system boots the data are invalid. When any register is written the data become valid        |
| TLB_PAGE_ID        |  2     | 2    | R/W              | R/W               | 0x0     | Peripheral ID (0: Hyper0, 1: Hyper1, 2: MRAM, 3 is invalid and can't be set) Shared with CFG_PAGE.PER_ID      |
| RESERVED           |  1     | 1    | R/W              | R/W               | 0x0     | Reserved for future use                                                                           |
| TLB_PAGE_CACHEABLE |  0     | 1    | R/W              | R/W               | 0x0     | Make icache aware of this page or not (shared with CFG_PAGEN)  Shared with CFG_PAGE.CACHEABLE     |


### CFG_TLB_PHYS_PAGE

If TLB mode is enabled this table is used in case of a miss only.

- When a miss occurs an address is assembled using the MSB bits
  from the TLB virtual address and the LSB bits from the physical one
  depending on the page size

#### Fields

| Field Name     | Offset | Size | Host Access Type | Block Access Type | Default | Description                                                                                       |
| -------------- | ---    | ---  | ---              | ---               | ---     | ------------------------------------------------------------------------------------------------- |
| TLB_PHYS_ADDR  |  0     | 32   | R/W              | R/W               | 0x0     | Physical address used along the virtual address in TLB to form the refill address in case of miss |


### CFG_XIP_LOCK_ATTR

set default/lock/unlock attribute on pages pointed by next fc data transactions

attribute values:
- 2'b00: default mode
- 2'b01: lock page of next fc data requests
- 2'b10: unlock page of next fc data requests

If a page is locked, it cannot be evicted: it is always hot in the cache.

#### Fields

| Field Name | Bit Position | Size | Host Access Type | IP access Type | Reset Value | Description                            |
| ---------- | ------------ | ---- | ---------------- | -------------- | ----------- | -------------------------------------- |
| type       | 0            | 2    | R/W              | R              | 0x0         | lock attribute             |




## Usage

Hyper/octo side:
- First open hyper or mram IP as usual & configure burst and such
- Set 'xip_en' bit in config

XIP side:
- Set configurations for chosen device (0: hyper0, 1: hyper1, 2:MRAM)
- First set virtual address start (between 0x20000000 and 0x2FFFFFFF)
- Then base external address (phys address in device)
- Set size (in pages)
- Page size: between 512B and 64KB
- then allocate L2 pages and set offset in CFG_PAGEX registers.

All addresses need to be aligned on chosen page size.

## Constraints

- Both external memory addresses, virtual pages addresses and l2 cache pages must start aligned
on corresponding device page size.
- Only Hyper_octo_SDIO0, Hyper_octo_SDIO1 and MRAM can be used as source for XIP.
- Live reconfiguration is not supported if executing or fetching data from XIP area.
To reconfigure use a dedicated code+data area in L2 to ensure atomicity. Also, flush icache.
- Address space maximum coverage is equal to 4K x PAGE_SIZE. This means that you will need
64KB pages to cover the whole address space
