import "package:flutter_test/flutter_test.dart";
import "package:recipe_forge_mobile/data/models/sync_models.dart";

void main() {
  test("sync envelope roundtrip serialization", () {
    const SyncEnvelope envelope = SyncEnvelope(
      syncProtocolVersion: 1,
      requestId: "req-1",
      sessionId: "sess-1",
      deviceId: "device-1",
      sentAtUtc: "2026-04-15T00:00:00Z",
      payload: <String, dynamic>{"changes": <dynamic>[]},
    );

    final Map<String, dynamic> json = envelope.toJson();
    final SyncEnvelope parsed = SyncEnvelope.fromJson(json);
    expect(parsed.syncProtocolVersion, 1);
    expect(parsed.requestId, "req-1");
    expect(parsed.payload["changes"], isA<List<dynamic>>());
  });
}

