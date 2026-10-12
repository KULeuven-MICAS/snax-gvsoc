# QSPI

## Description
Features:
- Master QSPI
- Slave SPI
  - can use quite the same commands as the master: TX/RX/duplex transfers
  - 1 bit MISO(SDO0)/MOSI(SDI1)
  - MSB first
  - 4 modes: CPOL=0/1, CPHA=0/1
  - 8-bit transfer
  - optional chip select, active low.

## Registers

| Register Name | Offset | Size | Register Type | Host Access Type | Block Access Type | Default | Description                        |
| ---           | ---    | ---  | ---           | ---              | ---               | ---     | ---                                |
| RX_DEST       | 0x00   | 8    | Config        | R/W              | R                 | 0xFF    | Stream ID for the RX uDMA channel  |
| TX_DEST       | 0x04   | 8    | Config        | R/W              | R                 | 0xFF    | Stream ID for the TX uDMA channel  |
| CMD_DEST      | 0x08   | 8    | Config        | R/W              | R                 | 0xFF    | Stream ID for the CMD uDMA channel |
| STATUS        | 0x30   | 7    | Config        | R                | W                 | 0x00    | Status register                    |
| CONFIG        | 0x34   | 3    | Config        | R/W              | R                 | 0x1     | Configuration register             |


### CONFIG

#### Fields 

| Field Name     | Offset | Size | Host Access Type | Block Access Type | Default | Description               |
| ---            | ---    | ---  | ---              | ---               | ---     | ---                       |
| SPI_SLAVE_MODE | 0      | 1    | R/W              | R                 | 1       | Enable SPI slave mode     |
| RX_OVRFLW_EN   | 1      | 1    | R/W              | R                 | 0       | Enable RX overflow event  |
| TX_UNDRFLW_EN  | 2      | 1    | R/W              | R                 | 0       | Enable TX underflow event |


### RX_DEST

#### Fields

| Field Name | Offset | Size | Host Access Type | Block Access Type | Default | Description |
| ---        | ---    | ---  | ---              | ---               | ---     | ---         |
| RX_DEST    | 0      | 8    | R/W              | R                 | 0xFF    | Stream ID for the RX uDMA channel. Default is 0xFF (channel disabled). |


### TX_DEST

#### Fields

| Field Name | Offset | Size | Host Access Type | Block Access Type | Default | Description |
| ---        | ---    | ---  | ---              | ---               | ---     | ---         |
| TX_DEST    | 0      | 8    | R/W              | R                 | 0xFF    | Stream ID for the TX uDMA channel. Default is 0xFF (channel disabled). |


### CMD_DEST

#### Fields

| Field Name | Offset | Size | Host Access Type | Block Access Type | Default | Description |
| ---        | ---    | ---  | ---              | ---               | ---     | ---         |
| CMD_DEST   | 0      | 8    | R/W              | R                 | 0xFF    | Stream ID for the CMD uDMA channel. Default is 0xFF (channel disabled). |


### STATUS

#### Fields

| Field Name         | Offset | Size | Host Access Type | Block Access Type | Default | Description                                                            |
| ---                | ---    | ---  | ---              | ---               | ---     | ---                                                                    |
| STATUS             | 0      | 4    | R                | W                 | 0       | Misc status                                                            |
| CMD_EVENT          | 4      | 1    | R                | W                 | 0       | Is set to 1 upon transmission of a command; write register to clear    |
| RX_OVERFLOW_EVENT  | 5      | 1    | R                | W                 | 0       | (slave only) Set to 1 in case of RX overflow; write register to clear  |
| TX_UNDERFLOW_EVENT | 6      | 1    | R                | W                 | 0       | (slave only) Set to 1 in case of TX underflow; write register to clear |



## SPI Commands

32-bit commands to be sent through command stream.
Slave or master mode must be configured beforehand in CONFIG register, for the commands to be interpreted properly.

### SPI micro-code

| Command Name        | Size | Command field | Paramater             | Description                                                                                    |
| ---                 | ---  | ---           | ---                   | ---                                                                                            |
| SPI_CMD_CFG         | 32   | 0x0           | Fields in 32-bit word | (Master only) Set the configuration for the SPI Master IP                                      |
| SPI_CMD_SOT         | 32   | 0x1           | Fields in 32-bit word | (Master only) Select the Chip Select (CS)                                                      |
| SPI_CMD_SEND_CMD    | 32   | 0x2           | Fields in 32-bit word | (Master only) Transmit up to 16 bits of data in the command word                               |
| SPI_CMD_DUMMY       | 32   | 0x4           | Fields in 32-bit word | (Master only) Receive a number of dummy bits (not sent to the RX interface)                    |
| SPI_CMD_WAIT        | 32   | 0x5           | Fields in 32-bit word | (Master only) Wait for an external event to move to the next instruction                       |
| SPI_CMD_TX_DATA     | 32   | 0x6           | Fields in 32-bit word | Transfer from master to slave (Master: send data; slave: receive data) -- max 64 kwords        |
| SPI_CMD_RX_DATA     | 32   | 0x7           | Fields in 32-bit word | Transfer from slave to master (Master: receive data; slave: send data) -- max 64 kwords        |
| SPI_CMD_RPT         | 32   | 0x8           | Fields in 32-bit word | (Master only) Repeat the commands from here to SPI_CMD_RPT_END command a given number of times |
| SPI_CMD_EOT         | 32   | 0x9           | Fields in 32-bit word | Clear the Chip Select (CS) after transfer                                                      |
| SPI_CMD_RPT_END     | 32   | 0xA           | Fields in 32-bit word | (Master only) End of the repeated command section                                              |
| SPI_CMD_RX_CHECK    | 32   | 0xB           | Fields in 32-bit word | (Master only) Check up to 16 bits of data against an expected value                            |
| SPI_CMD_FULL_DUPLEX | 32   | 0xC           | Fields in 32-bit word | Transfer in full duplex mode (send and receive data) -- max 64 kwords                          |
| SPI_CMD_SETUP_AG    | 32   | 0xD           | Fields in 32-bit word | Setup a register of the address generator (the register value is given in the following word)  |



#### SPI_CMD_CFG

##### Fields

| Field Name         | Offset | Size | Value | Description                           |
| ---                | ---    | ---  | ---   | ---                                   |
| CLKDIV             | 0      | 8    | ARG   | Clock divider value                   |
| CPHA               | 8      | 1    | ARG   | Clock phase (CPHA) value              |
| CPOL               | 9      | 1    | ARG   | Clock polarity (CPOL) value           |
| SPI_CMD            | 28     | 4    | 0x0   | Command code -- here “CFG”=0x0        |


#### SPI_CMD_SOT

##### Fields

| Field Name   | Offset | Size | Value   |Description                     |
| ---          | ---    | ---  | ---     |---                             |
| CS           | 0      | 2    | ARG     | Select the Chip Select (CS): b00: csn0; b01: csn1; b10: csn2; b11: csn3 |
| CYCLE_COUNT  | 8      | 8    | ARG     | Number of wait cycles          |
| SPI_CMD      | 28     | 4    | 0x1     | Command code -- here “SOT”=0x1 |


#### SPI_CMD_SEND_CMD

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| DATA_VALUE   | 0      | 16   | ARG     | Value to be sent through the command. MSB must always be at bit 15, even if less than 16 bits are to be sent |
| DATA_SIZE    | 16     | 4    | ARG     | Size in bits of the value to be sent, minus 1 |
| QPI          | 27     | 1    | ARG     | Set to 1 to use quadSPI |
| SPI_CMD      | 28     | 4    | 0x2     | Command code -- here “SEND_CMD”=0x2 |


#### SPI_CMD_DUMMY

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| DUMMY_CYCLE  | 16     | 5    | ARG     | Number of dummy cycles to perform |
| QPI          | 27     | 1    | ARG     | Set to 1 to use quadSPI |
| SPI_CMD      | 28     | 4    | 0x4     | Command code -- here “DUMMY”=0x4 |


#### SPI_CMD_WAIT

##### Fields

| Field Name           | Offset | Size | Value   | Description |
| ---                  | ---    | ---  | ---     | ---         |
| EVENT_ID_CYCLE_COUNT | 0      | 8    | ARG     | External event id or Number of wait cycles |
| WAIT_TYPE            | 8      | 2    | ARG     | Type of wait: b00: wait for a soc event selected by EVENT_ID; ’b01: wait for CYCLE_COUNT cycles; b10: reserved; b11: reserved |
| SPI_CMD              | 28     | 4    | 0x5     | Command code -- here “WAIT”=0x5 |



#### SPI_CMD_TX_DATA

##### Fields

| Field Name      | Offset | Size | Value   | Description |
| ---             | ---    | ---  | ---     | ---         |
| WORD_NUM        | 0      | 16   | ARG     | Number of words (max 64K) to send (master) or receive (slave), minus 1. The number of bits sent depends on the word size. |
| IGNORE_SELECT   | 16     | 1    | ARG     | (Slave only) Set to 1 to ignore slave select |
| WORD_SIZE       | 16     | 5    | ARG     | (Master only) Size in bits, minus 1, of data words to send. Each word is read from L2 with a transfer of a configurable size (see WORD_PER_TRANSF field). |
| WORD_PER_TRANSF | 21     | 2    | ARG     | (Master only) Number of bytes transferred from L2 at each transfer: b00: 1 byte per transfer; 01: 2 bytes per transfer; b10: 4 bytes per transfer; b11: reserved. Using unaligned values between WORD_SIZE and WORD_PER_TRANSF can be used to insert dummy bits and drop bits, compared to L2 content. |
| LSB             | 26     | 1    | ARG     | (Master only) Set to 1 to use least-significant-bit-first transfers |
| QPI             | 27     | 1    | ARG     | (Master only) Set to 1 to use quadSPI |
| SPI_CMD         | 28     | 4    | 0x6     | Command code -- here “TX_DATA”=0x6 |


#### SPI_CMD_RX_DATA

##### Fields

| Field Name      | Offset | Size | Value   | Description |
| ---             | ---    | ---  | ---     | ---         |
| WORD_NUM        | 0      | 16   | ARG     | Number of words (max 64K) to receive master) or send (slave), minus 1. The number of bits received depends on the word size. |
| IGNORE_SELECT   | 16     | 1    | ARG     | (Slave only) Set to 1 to ignore slave select |
| WORD_SIZE       | 16     | 5    | ARG     | (Master only) Size in bits, minus 1, of data words to receive. |
| WORD_PER_TRANSF | 21     | 2    | ARG     | (Master only) Number of received words transferred to L2 in a single transfer: b00: 1 word per transfer; 01: 2 words per transfer; b10: 4 words per transfer; b11: reserved. A uDMA transfer to L2 is always 32-bit. To build it, WORD_SIZE is rounded-up to the closest supported word size (8, 16 or 32 bits), and the configured number of words are then packed. If the rounded word size multiplied by this field is not equal to 32 bits, then either dummy bits are inserted, or exceeding bits are dropped. |
| LSB             | 26     | 1    | ARG     | (Master only) Set to 1 to use least-significant-bit-first transfers |
| QPI             | 27     | 1    | ARG     | (Master only) Use quadSPI mode |
| SPI_CMD         | 28     | 4    | 0x7     | Command code -- here “RX_DATA”=0x7 |


#### SPI_CMD_RPT

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| RPT_CNT      | 0      | 16   | ARG     | Number of repeat iterations (max 64K) |
| SPI_CMD      | 28     | 4    | 0x8     | Command code -- here “RPT”=0x8 |


#### SPI_CMD_EOT

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| EVENT_GEN    | 0      | 1    | ARG     | Enable generation of EOT events: 0: disabled; 1: enabled |
| CS_KEEP      | 1      | 1    | ARG     | Keep chip-select active: 0: CS is released (high) at the end of the transfer: 1: CS is kept active (low) after the transfer is finished |
| SPI_CMD      | 28     | 4    | 0x9     | Command code -- here “EOT”=0x9 |


#### SPI_CMD_RPT_END

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| SPI_CMD      | 28     | 4    | 0xA     | Command code -- here “RPT_END”=0xA |


#### SPI_CMD_RX_CHECK

##### Fields

| Field Name   | Offset | Size | Value   | Description |
| ---          | ---    | ---  | ---     | ---         |
| COMP_DATA    | 0      | 16   | ARG     | Data value to compare (max 16 bits) |
| STATUS_SIZE  | 16     | 4    | ARG     | Size in bits of the value to check, minus 1 |
| CHECK_TYPE   | 24     | 2    | ARG     | Type of check: b00: compare all bits; b01: compare only ones; b10: compare only zeros; b11: reserved |
| LSB          | 26     | 1    | ARG     | Set to 1 to use least-significant-bit-first transfers |
| QPI          | 27     | 1    | ARG     | Set to 1 to use quadSPI |
| SPI_CMD      | 28     | 4    | 0xB     | Command code -- here “RX_CHECK”=0xB |


#### SPI_CMD_FULL_DUPLEX

##### Fields

| Field Name      | Offset | Size | Value   | Description |
| ---             | ---    | ---  | ---     | ---         |
| WORD_NUM        | 0      | 16   | ARG     | Number of words (max 64K) to send and receive, minus 1. The number of bits received and sent depends on the word size. |
| IGNORE_SELECT   | 16     | 1    | ARG     | (Slave only) Set to 1 to ignore slave select |
| WORD_SIZE       | 16     | 5    | ARG     | (Master only) Size in bits, minus 1, of data words to send and receive |
| WORD_PER_TRANSF | 21     | 2    | ARG     | (Master only) Number of words transferred from L2 at each transfer: b00: 1 byte per transfer; 01: 2 bytes per transfer; b10: 4 bytes per transfer; b11: reserved. A uDMA transfer to L2 is always 32-bit. To build it, WORD_SIZE is rounded-up to the closest supported word size (8, 16 or 32 bits), and the configured number of words are then packed. If the rounded word size multiplied by this field is not equal to 32 bits, then either dummy bits are inserted, or exceeding bits are dropped. |
| LSB             | 26     | 1    | ARG     | (Master only) Set to 1 to use least-significant-bit-first transfers |
| SPI_CMD         | 28     | 4    | 0xC     | Command code -- here “FULL_DUPLEX”=0xC |


#### SPI_CMD_SETUP_AG

##### Fields

| Field Name    | Offset | Size | Value   | Description |
| ---           | ---    | ---  | ---     | ---         |
| REG_SELECT    | 0      | 3    | ARG     | Register address to set. Configuration data is taken in the following word. |
| STREAM_SELECT | 8      | 1    | ARG     | Selects which address generator to set: 0: use stream ID of the RX channel; 1: use stream ID of the TX channel |
| SPI_CMD       | 28     | 4    | 0xD     | Command code -- here “SETUP_AG”=0xD |
