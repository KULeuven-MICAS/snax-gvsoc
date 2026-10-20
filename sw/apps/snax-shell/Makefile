# Builds the shell program, with snax-alu's library (the streamer's setup)
# and forge/vecadd/include/'s headers (the streamer's and the shell's CSRs),
# from sw/ (../../common.mk) into build/sw/apps/snax-shell/. It runs on
# snax_hjson with forge/vecadd/snax_alu.hjson. data.h is snax-alu's
# datagen.py (add, mode 0) at DATA_LEN 192, NumPy seed 0, as snax-alu's
# Makefile makes it.

APP      = snax-shell
DATA_LEN = 192
FORGE    = $(abspath $(CURDIR)/../../../forge/vecadd)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(FORGE)/include
INCDIRS += $(ALU_INCDIR)
LIB_OBJS = $(ALU_LIB)
include ../../common.mk

DATA_H = $(BUILDDIR)/data.h

# The Makefile too, for DATA_LEN
$(DATA_H): $(APP_DIR)/../snax-alu/data/datagen.py $(APP_DIR)/Makefile | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 -c "import sys, runpy, numpy as np; \
	np.random.seed(0); sys.argv = ['datagen.py', '--mode=0', '--length=$(DATA_LEN)']; \
	runpy.run_path('$<', run_name='__main__')" > $@

$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(wildcard $(FORGE)/include/*) $(LIB_OBJS) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
