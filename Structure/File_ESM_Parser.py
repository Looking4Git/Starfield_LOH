"""Fassade für den ESM-Parser zur Wahrung der Abwärtskompatibilität."""

from Structure.File_ESM_Parser_Base import (
    parse_tes4_header,
    get_num_masters,
    get_masters_list
)
from Structure.File_ESM_Parser_Body_Handles import (
    scan_esm_for_handles,
    CORE_POINTER_COLS,
    MOD_POINTER_COLS,
    POINTER_COLS
)
