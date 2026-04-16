class SyncEnvelope {
  final int syncProtocolVersion;
  final String requestId;
  final String sessionId;
  final String deviceId;
  final String sentAtUtc;
  final Map<String, dynamic> payload;
  final List<Map<String, dynamic>> errors;

  const SyncEnvelope({
    required this.syncProtocolVersion,
    required this.requestId,
    required this.sessionId,
    required this.deviceId,
    required this.sentAtUtc,
    required this.payload,
    this.errors = const [],
  });

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      "sync_protocol_version": syncProtocolVersion,
      "request_id": requestId,
      "session_id": sessionId,
      "device_id": deviceId,
      "sent_at_utc": sentAtUtc,
      "payload": payload,
      "errors": errors,
    };
  }

  factory SyncEnvelope.fromJson(Map<String, dynamic> json) {
    return SyncEnvelope(
      syncProtocolVersion: json["sync_protocol_version"] as int,
      requestId: json["request_id"] as String,
      sessionId: json["session_id"] as String,
      deviceId: json["device_id"] as String,
      sentAtUtc: json["sent_at_utc"] as String,
      payload: (json["payload"] as Map).cast<String, dynamic>(),
      errors: ((json["errors"] as List?) ?? const <dynamic>[])
          .map((dynamic e) => (e as Map).cast<String, dynamic>())
          .toList(),
    );
  }
}

class SyncStatus {
  final bool success;
  final String message;
  final String? lastSyncAtUtc;
  final int appliedChanges;
  final int conflicts;

  const SyncStatus({
    required this.success,
    required this.message,
    this.lastSyncAtUtc,
    this.appliedChanges = 0,
    this.conflicts = 0,
  });
}

