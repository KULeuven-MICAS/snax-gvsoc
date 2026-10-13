# Installs the SNAX targets and generators where gvrun looks for them, as
# pulp/CMakeLists.txt does for pulp's.
install(DIRECTORY . DESTINATION ${CMAKE_INSTALL_PREFIX}/generators
    FILES_MATCHING PATTERN "*.py" PATTERN __pycache__ EXCLUDE)
