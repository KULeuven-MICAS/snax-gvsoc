project(pulpos)

install(DIRECTORY "python"
        DESTINATION "${CMAKE_INSTALL_PREFIX}")

# Generate the per-target PulpOS make rules (bforge) at install time, for
# every target the SDK builds.  The PulpOS ports are the directories next to
# this one (each provides python/pulpos/<target>.py, and a build.py when it
# supports the make flow); the helper maps each target to its port and skips
# the targets without one.  This runs after gvsoc's install rules
# (add_subdirectory order in the top-level CMakeLists.txt), so
# install/targets, install/generators and install/python are populated.
# The generator lives in the build_tree submodule, which not every SDK checks
# out; the rules are only generated when it is there.
set(PULPOS_RULES_SCRIPT
    ${CMAKE_CURRENT_SOURCE_DIR}/../build_tree/scripts/generate_target_rules.py)
if(DEFINED GVSOC_TARGETS AND EXISTS ${PULPOS_RULES_SCRIPT})
    string(REPLACE " " ";" PULPOS_RULES_TARGETS "${GVSOC_TARGETS}")
    file(GLOB PULPOS_PORTS LIST_DIRECTORIES true ${CMAKE_CURRENT_SOURCE_DIR}/../*)
    install(CODE "
        execute_process(
            COMMAND python3 ${PULPOS_RULES_SCRIPT}
                --install-dir ${CMAKE_INSTALL_PREFIX}
                --repo-root ${CMAKE_SOURCE_DIR}
                --ports ${PULPOS_PORTS}
                --targets ${PULPOS_RULES_TARGETS}
            RESULT_VARIABLE pulpos_rules_ret)
        if(NOT pulpos_rules_ret EQUAL 0)
            message(FATAL_ERROR \"PulpOS make-rules generation failed\")
        endif()")
endif()
