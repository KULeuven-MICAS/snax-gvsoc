Usage
-----

The GVSOC simulation launch process is handled by *gvrun*. This runner manages the full
application lifecycle on GVSOC: compiling the application, producing flash images, and launching
the simulation. Custom options can be specified to utilize GVSOC-specific features, such as
trace management.

Specifying the Target
.....................

Since the same generic GVSOC engine is compiled once for all supported targets, the target to be
simulated must be specified using the ``--target`` option: ::

  gvrun --target rv64

The target tells GVSOC which system must be simulated. It corresponds to a Python generator
which will be called to instantiate the set of components which will simulate the target
system. In this example, the ``rv64`` system instantiates a generic RISC-V 64-bit system with a single
memory which is able to boot Linux.

Specifying Target Directories
.............................

Since targets are chip-dependent, gvrun needs to know where the possible targets can be found
through the ``--target-dir`` option. As the target is a Python script, called a generator, which
will use other Python scripts to instantiate the full architecture, this option can be used several
times to specify multiple paths.

When gvrun is launched from the SDK installation, target and model directories are
auto-discovered from the ``install/`` folder. Explicit paths are only needed in custom setups: ::

  gvrun --target gap.gap9.evk --target-dir=$GAP_SDK_HOME/gvsoc/gvsoc_gap --target-dir=$GAP_SDK_HOME/gvsoc/gvsoc/models

Specifying Model Directories
............................

Since models are compiled separately from the engine as shared libraries and dynamically loaded
by the engine when the target system is instantiated, some additional options might be needed
to give the paths to these models: ::

  gvrun --target gap.gap9.evk --model-dir=$GAP_SDK_HOME/install/workstation/models

Specifying the Working Directory
................................

As GVSOC will generate several temporary files, it is also good to launch it from a specific folder
or to specify it through the ``--work-dir`` option: ::

  gvrun --target rv64 --work-dir=build

Viewing available Options
.........................

The list of available options can be displayed using the ``--help`` option. Since options can differ
depending on the target or other options, it is important to execute it with the
full command-line: ::

  gvrun --target rv64 --help

Specifying the Application Binary
.................................

The application binary to be simulated can be specified using the ``--parameter`` option, which is
not relevant for all targets: ::

  gvrun --target rv64 --parameter binary=test.elf

Running Commands
................

gvrun manages all that is needed to execute an application on the target, like
compiling the application and producing flash images. It must be told the list of commands to be
executed. Here are a few examples: ::

  gvrun --target rv64 --parameter binary=test.elf run

  gvrun --target gap.gap9.evk --work-dir=build build run
