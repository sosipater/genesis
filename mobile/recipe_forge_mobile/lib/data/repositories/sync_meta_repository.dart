import "package:shared_preferences/shared_preferences.dart";

class SyncMetaRepository {
  static const String _hostKey = "sync.host";
  static const String _lastStatusKey = "sync.last_status";
  static const String _lastSyncAtKey = "sync.last_sync_at";
  static const String _cursorKey = "sync.cursor";

  Future<String?> getHost() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString(_hostKey);
  }

  Future<void> setHost(String host) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(_hostKey, host);
  }

  Future<void> setLastStatus(String message, {String? syncedAtUtc}) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(_lastStatusKey, message);
    if (syncedAtUtc != null) {
      await prefs.setString(_lastSyncAtKey, syncedAtUtc);
    }
  }

  Future<String?> getLastStatus() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString(_lastStatusKey);
  }

  Future<String?> getLastSyncAt() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString(_lastSyncAtKey);
  }

  Future<String?> getCursor() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    return prefs.getString(_cursorKey);
  }

  Future<void> setCursor(String cursor) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(_cursorKey, cursor);
  }
}

