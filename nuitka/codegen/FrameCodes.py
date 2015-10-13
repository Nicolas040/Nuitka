#     Copyright 2015, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Frame codes

This is about frame stacks and their management. There are different kinds
of frames for different uses.
"""


from nuitka.utils.Utils import python_version

from . import Emission
from .ExceptionCodes import getTracebackMakingIdentifier
from .GlobalsLocalsCodes import getLoadLocalsCode
from .Indentation import indented
from .ModuleCodes import getModuleAccessCode
from .templates.CodeTemplatesFrames import (
    template_frame_guard_cache_decl,
    template_frame_guard_frame_decl,
    template_frame_guard_full_block,
    template_frame_guard_full_exception_handler,
    template_frame_guard_full_return_handler,
    template_frame_guard_generator,
    template_frame_guard_generator_exception_handler,
    template_frame_guard_generator_return_handler,
    template_frame_guard_once
)


def getFrameGuardHeavyCode(frame_identifier, code_identifier, codes,
                           needs_preserve, parent_exception_exit,
                           parent_return_exit, frame_exception_exit,
                           frame_return_exit, provider, context):
    no_exception_exit = context.allocateLabel("frame_no_exception")

    context.addFrameDeclaration(
        template_frame_guard_cache_decl % {
            "frame_identifier" : frame_identifier,
        }
    )
    context.addFrameDeclaration(
        template_frame_guard_frame_decl % {
            "frame_identifier" : frame_identifier,
        }
    )

    result = template_frame_guard_full_block % {
        "frame_identifier"  : frame_identifier,
        "code_identifier"   : code_identifier,
        "codes"             : indented(codes, 0),
        "module_identifier" : getModuleAccessCode(context = context),
        "no_exception_exit" : no_exception_exit,
        "needs_preserve"    : 1 if needs_preserve else 0,
    }

    if frame_return_exit is not None:
        result += template_frame_guard_full_return_handler % {
            "frame_identifier"  : frame_identifier,
            "return_exit"       : parent_return_exit,
            "frame_return_exit" : frame_return_exit,
            "needs_preserve"    : 1 if needs_preserve else 0,
        }


    if frame_exception_exit is not None:
        frame_locals_name, locals_code = getFrameLocalsUpdateCode(
            provider = provider,
            context  = context
        )

        result += template_frame_guard_full_exception_handler % {
            "frame_identifier"      : frame_identifier,
            "frame_locals_name"     : frame_locals_name,
            "store_frame_locals"    : indented(
                locals_code,
                2,
                vert_block = True
            ),
            "tb_making"             : getTracebackMakingIdentifier(
                                          context     = context,
                                          lineno_name = "exception_lineno"
                                      ),
            "parent_exception_exit" : parent_exception_exit,
            "frame_exception_exit"  : frame_exception_exit,
            "needs_preserve"        : 1 if needs_preserve else 0,
        }

    result += "%s:;\n" % no_exception_exit

    return result


def getFrameGuardOnceCode(frame_identifier, code_identifier,
                          codes, parent_exception_exit, parent_return_exit,
                          frame_exception_exit, frame_return_exit,
                          needs_preserve, provider, context):
    # Used for modules only currently, but that ought to change.
    assert parent_return_exit is None and frame_return_exit is None

    if not provider.isCompiledPythonModule():
        _frame_locals_name, locals_code = getFrameLocalsUpdateCode(
            provider = provider,
            context  = context
        )

        # TODO: Not using locals, which is only OK for modules
        assert False, locals_code

    context.addFrameDeclaration(
        template_frame_guard_frame_decl % {
            "frame_identifier" : frame_identifier,
        }
    )

    return template_frame_guard_once % {
        "frame_identifier"      : frame_identifier,
        "code_identifier"       : code_identifier,
        "codes"                 : indented(codes, 0),
        "module_identifier"     : getModuleAccessCode(context = context),
        "tb_making"             : getTracebackMakingIdentifier(
                                     context     = context,
                                     lineno_name = "exception_lineno"
                                  ),
        "parent_exception_exit" : parent_exception_exit,
        "frame_exception_exit"  : frame_exception_exit,
        "no_exception_exit"     : context.allocateLabel(
            "frame_no_exception"
        ),
        "needs_preserve"        : 1 if needs_preserve else 0
    }


def getFrameGuardLightCode(frame_identifier, code_identifier, codes,
                           parent_exception_exit, parent_return_exit,
                           frame_exception_exit, frame_return_exit,
                           provider, context):
    context.markAsNeedsExceptionVariables()

    assert frame_exception_exit is not None

    context.addFrameDeclaration(
        template_frame_guard_cache_decl % {
            "frame_identifier" : frame_identifier,
        }
    )

    context.addFrameDeclaration(
        template_frame_guard_frame_decl % {
            "frame_identifier" : frame_identifier,
        }
    )

    no_exception_exit = context.allocateLabel("frame_no_exception")

    result = template_frame_guard_generator % {
        "frame_identifier"      : frame_identifier,
        "code_identifier"       : code_identifier,
        "codes"                 : indented(codes, 0),
        "module_identifier"     : getModuleAccessCode(context = context),
        "no_exception_exit"     : no_exception_exit,
    }

    if frame_return_exit is not None:
        result += template_frame_guard_generator_return_handler % {
            "frame_identifier"  : frame_identifier,
            "return_exit"       : parent_return_exit,
            "frame_return_exit" : frame_return_exit,
        }

    frame_locals_name, locals_code = getFrameLocalsUpdateCode(
        provider = provider,
        context  = context
    )

    # TODO: Don't create locals for StopIteration or GeneratorExit, that is just
    # wasteful.
    result += template_frame_guard_generator_exception_handler % {
        "frame_identifier"      : frame_identifier,
        "frame_locals_name"     : frame_locals_name,
        "store_frame_locals"    : indented(
            locals_code,
            2,
            vert_block = True
        ),
        "tb_making"             : getTracebackMakingIdentifier(
                                      context     = context,
                                      lineno_name = "exception_lineno"
                                  ),
        "frame_exception_exit"  : frame_exception_exit,
        "parent_exception_exit" : parent_exception_exit,
        "no_exception_exit"     : no_exception_exit,
    }

    return result


def getFrameLocalsUpdateCode(provider, context):
    locals_codes = Emission.SourceCodeCollector()

    context.setCurrentSourceCodeReference(
        provider.getSourceReference()
    )

    frame_locals_name = context.allocateTempName(
        "frame_locals",
        unique = True
    )

    getLoadLocalsCode(
        to_name  = frame_locals_name,
        provider = provider,
        mode     = "updated",
        emit     = locals_codes.emit,
        context  = context
    )

    if context.needsCleanup(frame_locals_name):
        context.removeCleanupTempName(frame_locals_name)

    return frame_locals_name, locals_codes.codes


def getFramePreserveExceptionCode(statement, emit, context):
    emit("// Preserve existing published exception.")

    if python_version < 300:
        emit(
            "PRESERVE_FRAME_EXCEPTION( %(frame_identifier)s );" % {
                "frame_identifier" : context.getFrameHandle()
            }
        )
    else:
        preserver_id = statement.getPreserverId()

        if preserver_id == 0 and python_version < 300:
            emit(
                "PRESERVE_FRAME_EXCEPTION( %(frame_identifier)s );" % {
                    "frame_identifier" : context.getFrameHandle()
                }
            )
        else:
            context.addExceptionPreserverVariables(preserver_id)

            emit(
                """\
exception_preserved_type_%(preserver_id)d = PyThreadState_GET()->exc_type;
Py_XINCREF( exception_preserved_type_%(preserver_id)d );
exception_preserved_value_%(preserver_id)d = PyThreadState_GET()->exc_value;
Py_XINCREF( exception_preserved_value_%(preserver_id)d );
exception_preserved_tb_%(preserver_id)d = (PyTracebackObject *)PyThreadState_GET()->exc_traceback;
Py_XINCREF( exception_preserved_tb_%(preserver_id)d );
""" % {
                    "preserver_id"  : preserver_id,
                }
            )


def getFrameRestoreExceptionCode(statement, emit, context):
    emit("// Restore previous exception.")

    if python_version < 300:
        emit(
            "RESTORE_FRAME_EXCEPTION( %(frame_identifier)s );" % {
                "frame_identifier" : context.getFrameHandle()
            }
        )
    else:
        preserver_id = statement.getPreserverId()

        if preserver_id == 0  and python_version < 300:
            emit(
                "RESTORE_FRAME_EXCEPTION( %(frame_identifier)s );" % {
                    "frame_identifier" : context.getFrameHandle()
                }
            )
        else:
            # pylint: disable=C0301

            emit(
                """\
SET_CURRENT_EXCEPTION( exception_preserved_type_%(preserver_id)d, exception_preserved_value_%(preserver_id)d, exception_preserved_tb_%(preserver_id)d );""" % {
                    "preserver_id" : preserver_id,
                }
            )
