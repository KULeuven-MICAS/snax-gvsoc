# Builds snax_cluster's snax-alu app (src/ and data/ are copies, sw/README.md)
# from sw/ (../../common.mk), with snax-alu's library, into
# build/sw/apps/snax-alu/<DATA_LEN>/. DATA_LEN (default 100, a multiple of
# 4) is the vector length: data.h is made there with datagen.py, NumPy seed
# 0, mode 0 (SG5).

APP      = snax-alu
DATA_LEN ?= 100
BUILDDIR = $(SW_BUILD)/apps/$(APP)/$(DATA_LEN)
INCDIRS  = $(BUILDDIR)
INCDIRS += $(ALU_INCDIR)
LIB_OBJS = $(ALU_LIB)
include ../../common.mk

DATA_H = $(BUILDDIR)/data.h

$(DATA_H): $(APP_DIR)/data/datagen.py | $(BUILDDIR)
	PYTHONPATH=$(SW)/util python3 -c "import sys, runpy, numpy as np; \
	np.random.seed(0); sys.argv = ['datagen.py', '--mode=0', '--length=$(DATA_LEN)']; \
	runpy.run_path('$<', run_name='__main__')" > $@

$(ELF): $(APP_DIR)/src/$(APP).c $(DATA_H) $(LIB_OBJS) $(LIBS) | $(BUILDDIR)
	$(RISCV_CC) $(RISCV_CFLAGS) $(RISCV_LDFLAGS) $< -o $@
