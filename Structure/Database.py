"""
Structure/Database.py
Zentrale Fassade für das Datenbank-Subsystem von Starfield LOH.

Re-exportiert alle Funktionen, Klassen und Konstanten aus den spezialisierten Modulen:
- Structure.Database_Core: DB-Verbindung, Transaktions-Context-Manager, Schema-Migrationen, Performance-Pragmas
- Structure.Database_Executions: Protokollierung von Skript-Läufen (LOH_Executions) und Update-Tracking (Mods_Updates)
- Structure.Database_Views: Erstellung und Abfrage von SQLite-Views (Konfliktmatrix, Kategoriedimensionen)
- Structure.Database_Profiles: Verwaltung von Benutzerprofilen, LoadOrder-Zuständen und Sorter-Ergebnissen
- Structure.Database_Mods: Verwaltung von Mods, Komponenten, Bildern, Lookups und Anforderungen

Gewährleistet 100%ige Abwärtskompatibilität für alle bestehenden Aufrufer im Projekt.
"""

from Structure.Database_Core import (
    TEMPLATE_DB_FILE,
    parse_version_tuple,
    is_version_newer_sql,
    get_db_connection,
    db_connection,
    db_cursor,
    ensure_default_database_mode,
    ensure_mods_updates_schema,
    ensure_mods_category_loot_schema,
    ensure_conflict_solution_types_schema,
    enable_db_performance_mode,
    restore_db_default_mode,
    init_sorter_results_table,
    init_loh_executions_table,
)

from Structure.Database_Executions import (
    get_execution_state_text,
    record_script_start,
    record_script_end,
    record_script_abort,
    record_script_execution,
    set_script_execution_manual,
    update_script_execution_state,
    update_script_execution_reason,
    get_script_last_execution,
    get_incomplete_mods_updates,
    clear_mods_updates,
    init_mods_updates,
    set_mod_update_state,
    apply_completed_mod_updates,
    get_all_mods_updates,
)

from Structure.Database_Views import (
    create_view_mods_conflicts_matrix,
    get_mod_conflicts_matrix,
    create_view_category_dimension_max,
)

from Structure.Database_Profiles import (
    get_profiles,
    get_load_order,
    update_load_order_active,
    create_profile,
    copy_profile,
    delete_profile,
    update_profile_description,
    update_load_order_positions,
    has_sorter_results,
    apply_sorter_to_profile,
    apply_sorter_to_all_profiles,
    check_sorter_prerequisites,
)

from Structure.Database_Mods import (
    get_mods_by_state,
    get_mods_with_updates,
    get_mod_image,
    save_mod_image_file,
    get_lookup_data,
    update_mod_details,
    check_component_exists,
    get_mod_by_id,
    get_components_by_mod_id,
    get_masterfiles_by_mod_id,
    get_component_details_for_ui,
    get_creation_categories_for_ui,
    get_mod_requirements_for_ui,
    get_mod_dependencies_for_ui,
    get_mod_conflicts_for_ui,
    delete_mod_requirement,
    get_installed_mods_with_components,
    add_mod_requirement,
    ensure_component_registered,
    update_mod_category_and_note,
    update_mod_category,
    get_mod_category_stats,
    update_mod_classifier_category,
    apply_all_classifier_categories,
    has_classifier_categories,
)

__all__ = [
    # Core
    "TEMPLATE_DB_FILE",
    "parse_version_tuple",
    "is_version_newer_sql",
    "get_db_connection",
    "db_connection",
    "db_cursor",
    "ensure_default_database_mode",
    "ensure_mods_updates_schema",
    "ensure_mods_category_loot_schema",
    "ensure_conflict_solution_types_schema",
    "enable_db_performance_mode",
    "restore_db_default_mode",
    "init_sorter_results_table",
    "init_loh_executions_table",
    # Executions
    "get_execution_state_text",
    "record_script_start",
    "record_script_end",
    "record_script_abort",
    "record_script_execution",
    "set_script_execution_manual",
    "update_script_execution_state",
    "update_script_execution_reason",
    "get_script_last_execution",
    "get_incomplete_mods_updates",
    "clear_mods_updates",
    "init_mods_updates",
    "set_mod_update_state",
    "apply_completed_mod_updates",
    "get_all_mods_updates",
    # Views
    "create_view_mods_conflicts_matrix",
    "get_mod_conflicts_matrix",
    "create_view_category_dimension_max",
    # Profiles
    "get_profiles",
    "get_load_order",
    "update_load_order_active",
    "create_profile",
    "copy_profile",
    "delete_profile",
    "update_profile_description",
    "update_load_order_positions",
    "has_sorter_results",
    "apply_sorter_to_profile",
    "apply_sorter_to_all_profiles",
    "check_sorter_prerequisites",
    # Mods
    "get_mods_by_state",
    "get_mods_with_updates",
    "get_mod_image",
    "save_mod_image_file",
    "get_lookup_data",
    "update_mod_details",
    "check_component_exists",
    "get_mod_by_id",
    "get_components_by_mod_id",
    "get_masterfiles_by_mod_id",
    "get_component_details_for_ui",
    "get_creation_categories_for_ui",
    "get_mod_requirements_for_ui",
    "get_mod_dependencies_for_ui",
    "get_mod_conflicts_for_ui",
    "delete_mod_requirement",
    "get_installed_mods_with_components",
    "add_mod_requirement",
    "ensure_component_registered",
    "update_mod_category_and_note",
    "update_mod_category",
    "get_mod_category_stats",
    "update_mod_classifier_category",
    "apply_all_classifier_categories",
    "has_classifier_categories",
]