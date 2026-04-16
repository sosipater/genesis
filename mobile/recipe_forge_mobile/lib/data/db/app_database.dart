import "package:path/path.dart" as p;
import "package:sqflite/sqflite.dart";

class AppDatabase {
  static const int schemaVersion = 10;
  Database? _db;

  Future<Database> get database async {
    if (_db != null) {
      return _db!;
    }
    final String databasesPath = await getDatabasesPath();
    final String dbPath = p.join(databasesPath, "recipe_forge_mobile.db");
    _db = await openDatabase(
      dbPath,
      version: schemaVersion,
      onCreate: (Database db, int version) async {
        await _createSchema(db);
      },
      onUpgrade: (Database db, int oldVersion, int newVersion) async {
        if (oldVersion < 2) {
          await db.execute("ALTER TABLE recipe_equipment ADD COLUMN notes TEXT NULL");
          await db.execute("ALTER TABLE recipe_equipment ADD COLUMN affiliate_url TEXT NULL");
          await db.execute("ALTER TABLE recipe_ingredients ADD COLUMN substitutions TEXT NULL");
          await db.execute("ALTER TABLE recipe_ingredients ADD COLUMN preparation_notes TEXT NULL");
        }
        if (oldVersion < 3) {
          await db.execute("""
            CREATE TABLE collections (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
          await db.execute("""
            CREATE TABLE collection_items (
              id TEXT PRIMARY KEY,
              collection_id TEXT NOT NULL,
              recipe_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              deleted_at TEXT NULL,
              UNIQUE(collection_id, recipe_id),
              FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
            )
          """);
          await db.execute("""
            CREATE TABLE working_set_items (
              id TEXT PRIMARY KEY,
              recipe_id TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
        }
        if (oldVersion < 4) {
          await db.execute("ALTER TABLE recipes ADD COLUMN servings REAL NULL");
          await db.execute("""
            CREATE TABLE meal_plans (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              start_date TEXT NULL,
              end_date TEXT NULL,
              notes TEXT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
          await db.execute("""
            CREATE TABLE meal_plan_items (
              id TEXT PRIMARY KEY,
              meal_plan_id TEXT NOT NULL,
              recipe_id TEXT NOT NULL,
              servings_override REAL NULL,
              notes TEXT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL,
              FOREIGN KEY(meal_plan_id) REFERENCES meal_plans(id) ON DELETE CASCADE
            )
          """);
          await db.execute("""
            CREATE TABLE grocery_lists (
              id TEXT PRIMARY KEY,
              meal_plan_id TEXT NULL,
              name TEXT NOT NULL,
              generated_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
          await db.execute("""
            CREATE TABLE grocery_list_items (
              id TEXT PRIMARY KEY,
              grocery_list_id TEXT NOT NULL,
              name TEXT NOT NULL,
              quantity_value REAL NULL,
              unit TEXT NULL,
              checked INTEGER NOT NULL DEFAULT 0,
              source_recipe_ids_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL,
              FOREIGN KEY(grocery_list_id) REFERENCES grocery_lists(id) ON DELETE CASCADE
            )
          """);
        }
        if (oldVersion < 5) {
          await db.execute("ALTER TABLE grocery_list_items ADD COLUMN source_type TEXT NOT NULL DEFAULT 'generated'");
          await db.execute("ALTER TABLE grocery_list_items ADD COLUMN generated_group_key TEXT NULL");
          await db.execute("ALTER TABLE grocery_list_items ADD COLUMN was_user_modified INTEGER NOT NULL DEFAULT 0");
          await db.execute("ALTER TABLE grocery_list_items ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0");
        }
        if (oldVersion < 6) {
          await db.execute("""
            CREATE TABLE recipe_user_state (
              recipe_id TEXT PRIMARY KEY,
              is_favorite INTEGER NOT NULL DEFAULT 0,
              last_opened_at TEXT NULL,
              last_cooked_at TEXT NULL,
              open_count INTEGER NOT NULL DEFAULT 0,
              cook_count INTEGER NOT NULL DEFAULT 0,
              pinned INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
        }
        if (oldVersion < 7) {
          await db.execute("ALTER TABLE recipes ADD COLUMN source_name TEXT NULL");
          await db.execute("ALTER TABLE recipes ADD COLUMN source_url TEXT NULL");
          await db.execute("ALTER TABLE recipes ADD COLUMN difficulty TEXT NULL");
          await db.execute("ALTER TABLE recipes ADD COLUMN prep_minutes INTEGER NULL");
          await db.execute("ALTER TABLE recipes ADD COLUMN cook_minutes INTEGER NULL");
          await db.execute("ALTER TABLE recipes ADD COLUMN total_minutes INTEGER NULL");
          await db.execute("ALTER TABLE step_timers ADD COLUMN alert_sound_key TEXT NULL");
        }
        if (oldVersion < 8) {
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN planned_date TEXT NULL");
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN meal_slot TEXT NULL");
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN slot_label TEXT NULL");
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0");
        }
        if (oldVersion < 9) {
          await db.execute("ALTER TABLE recipes ADD COLUMN cover_media_id TEXT NULL");
          await db.execute("ALTER TABLE recipe_equipment ADD COLUMN media_id TEXT NULL");
          await db.execute("ALTER TABLE recipe_ingredients ADD COLUMN media_id TEXT NULL");
          await db.execute("ALTER TABLE recipe_steps ADD COLUMN media_id TEXT NULL");
          await db.execute("""
            CREATE TABLE media_assets (
              id TEXT PRIMARY KEY,
              owner_type TEXT NOT NULL,
              owner_id TEXT NOT NULL,
              file_name TEXT NOT NULL,
              mime_type TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              width INTEGER NULL,
              height INTEGER NULL,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
        }
        if (oldVersion < 10) {
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN reminder_enabled INTEGER NOT NULL DEFAULT 0");
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN pre_reminder_minutes INTEGER NULL");
          await db.execute("ALTER TABLE meal_plan_items ADD COLUMN start_cooking_prompt INTEGER NOT NULL DEFAULT 0");
          await db.execute("""
            CREATE TABLE reminder_notifications (
              id TEXT PRIMARY KEY,
              type TEXT NOT NULL,
              reference_type TEXT NOT NULL,
              reference_id TEXT NOT NULL,
              scheduled_time_utc TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              enabled INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL,
              deleted_at TEXT NULL
            )
          """);
        }
      },
    );
    await _db!.execute("PRAGMA foreign_keys = ON");
    return _db!;
  }

  Future<void> _createSchema(Database db) async {
    await db.execute("""
      CREATE TABLE recipes (
        id TEXT PRIMARY KEY,
        scope TEXT NOT NULL,
        title TEXT NOT NULL,
        subtitle TEXT NULL,
        author TEXT NULL,
        source_name TEXT NULL,
        source_url TEXT NULL,
        difficulty TEXT NULL,
        notes TEXT NULL,
        servings REAL NULL,
        prep_minutes INTEGER NULL,
        cook_minutes INTEGER NULL,
        total_minutes INTEGER NULL,
        cover_media_id TEXT NULL,
        status TEXT NOT NULL,
        updated_at TEXT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE recipe_equipment (
        id TEXT PRIMARY KEY,
        recipe_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NULL,
        notes TEXT NULL,
        affiliate_url TEXT NULL,
        media_id TEXT NULL,
        is_required INTEGER NOT NULL,
        display_order INTEGER NOT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE recipe_ingredients (
        id TEXT PRIMARY KEY,
        recipe_id TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        quantity_value REAL NULL,
        unit TEXT NULL,
        ingredient_name TEXT NULL,
        substitutions TEXT NULL,
        preparation_notes TEXT NULL,
        media_id TEXT NULL,
        is_optional INTEGER NOT NULL,
        display_order INTEGER NOT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE recipe_steps (
        id TEXT PRIMARY KEY,
        recipe_id TEXT NOT NULL,
        title TEXT NULL,
        body_text TEXT NOT NULL,
        step_type TEXT NOT NULL,
        estimated_seconds INTEGER NULL,
        media_id TEXT NULL,
        display_order INTEGER NOT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE media_assets (
        id TEXT PRIMARY KEY,
        owner_type TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        mime_type TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        width INTEGER NULL,
        height INTEGER NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE step_links (
        id TEXT PRIMARY KEY,
        step_id TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        token_key TEXT NOT NULL,
        label_snapshot TEXT NOT NULL,
        label_override TEXT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(step_id) REFERENCES recipe_steps(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE step_timers (
        id TEXT PRIMARY KEY,
        step_id TEXT NOT NULL,
        label TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL,
        auto_start INTEGER NOT NULL,
        alert_sound_key TEXT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(step_id) REFERENCES recipe_steps(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE recent_recipes (
        recipe_id TEXT PRIMARY KEY,
        opened_at TEXT NOT NULL,
        FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE collections (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE collection_items (
        id TEXT PRIMARY KEY,
        collection_id TEXT NOT NULL,
        recipe_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        deleted_at TEXT NULL,
        UNIQUE(collection_id, recipe_id),
        FOREIGN KEY(collection_id) REFERENCES collections(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE working_set_items (
        id TEXT PRIMARY KEY,
        recipe_id TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE meal_plans (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        start_date TEXT NULL,
        end_date TEXT NULL,
        notes TEXT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE meal_plan_items (
        id TEXT PRIMARY KEY,
        meal_plan_id TEXT NOT NULL,
        recipe_id TEXT NOT NULL,
        servings_override REAL NULL,
        notes TEXT NULL,
        planned_date TEXT NULL,
        meal_slot TEXT NULL,
        slot_label TEXT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        reminder_enabled INTEGER NOT NULL DEFAULT 0,
        pre_reminder_minutes INTEGER NULL,
        start_cooking_prompt INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(meal_plan_id) REFERENCES meal_plans(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE reminder_notifications (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        reference_type TEXT NOT NULL,
        reference_id TEXT NOT NULL,
        scheduled_time_utc TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE grocery_lists (
        id TEXT PRIMARY KEY,
        meal_plan_id TEXT NULL,
        name TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
    await db.execute("""
      CREATE TABLE grocery_list_items (
        id TEXT PRIMARY KEY,
        grocery_list_id TEXT NOT NULL,
        name TEXT NOT NULL,
        quantity_value REAL NULL,
        unit TEXT NULL,
        checked INTEGER NOT NULL DEFAULT 0,
        source_recipe_ids_json TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'generated',
        generated_group_key TEXT NULL,
        was_user_modified INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL,
        FOREIGN KEY(grocery_list_id) REFERENCES grocery_lists(id) ON DELETE CASCADE
      )
    """);
    await db.execute("""
      CREATE TABLE recipe_user_state (
        recipe_id TEXT PRIMARY KEY,
        is_favorite INTEGER NOT NULL DEFAULT 0,
        last_opened_at TEXT NULL,
        last_cooked_at TEXT NULL,
        open_count INTEGER NOT NULL DEFAULT 0,
        cook_count INTEGER NOT NULL DEFAULT 0,
        pinned INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        deleted_at TEXT NULL
      )
    """);
  }
}

