import "package:flutter/foundation.dart";

import "../../config/app_config.dart";
import "../../data/models/sync_models.dart";
import "../../data/repositories/sync_meta_repository.dart";
import "../../data/sync/sync_service.dart";

class SyncController extends ChangeNotifier {
  final SyncService _syncService;
  final SyncMetaRepository _metaRepository;

  SyncController(this._syncService, this._metaRepository);

  String host = kAppConfig.defaultHost;
  String? lastStatus;
  String? lastSyncAtUtc;
  bool running = false;

  Future<void> load() async {
    host = (await _metaRepository.getHost()) ?? kAppConfig.defaultHost;
    lastStatus = await _metaRepository.getLastStatus();
    lastSyncAtUtc = await _metaRepository.getLastSyncAt();
    notifyListeners();
  }

  Future<void> updateHost(String value) async {
    host = value.trim();
    await _metaRepository.setHost(host);
    notifyListeners();
  }

  Future<SyncStatus> testConnection() async {
    running = true;
    notifyListeners();
    final SyncStatus status = await _syncService.testConnection(host);
    lastStatus = status.message;
    running = false;
    notifyListeners();
    return status;
  }

  Future<SyncStatus> syncNow() async {
    running = true;
    notifyListeners();
    final SyncStatus status = await _syncService.runSync(host);
    lastStatus = status.message;
    lastSyncAtUtc = status.lastSyncAtUtc ?? lastSyncAtUtc;
    running = false;
    notifyListeners();
    return status;
  }
}

