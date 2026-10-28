# Installs the SNAX targets and generators where gvrun looks for them, as
# pulp/CMakeLists.txt does for pulp's.
install(DIRECTORY . DESTINATION ${CMAKE_INSTALL_PREFIX}/generators
    FILES_MATCHING PATTERN "*.py" PATTERN __pycache__ EXCLUDE)

# The cluster files of sw/cfg/ (snax_cluster's), beside the targets that
# read them by name (snax_hjson.py's CFG_DIRS)
install(DIRECTORY ../sw/cfg/ DESTINATION ${CMAKE_INSTALL_PREFIX}/generators/cfg
    FILES_MATCHING PATTERN "*.hjson")

# The snax_hjson target's default (snax_hjson.py's DEFAULT_HJSON): forge/vecadd/'s
# cluster, streamer file and accelerator.json, snax-forge's vecadd fixture
install(DIRECTORY ../forge/vecadd/ DESTINATION ${CMAKE_INSTALL_PREFIX}/generators/cfg/forge/vecadd
    FILES_MATCHING PATTERN "*.hjson" PATTERN "accelerator.json")
