#
# "main" pseudo-component makefile.
#
# (Uses default behaviour of compiling all source files in directory, adding 'include' to include path.)

# Embed the HTML file as binary symbols
COMPONENT_EMBED_TXTFILES := index.html

COMPONENT_SRCS := main.c info.c flash.c backup.c common.c
COMPONENT_ADD_INCLUDEDIRS := .
