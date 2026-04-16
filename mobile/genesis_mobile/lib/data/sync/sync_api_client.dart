import "dart:convert";

import "package:http/http.dart" as http;

import "../models/sync_models.dart";

class SyncApiClient {
  final http.Client _httpClient;

  SyncApiClient(this._httpClient);

  Future<Map<String, dynamic>> health(String host) async {
    final Uri uri = Uri.parse("$host/health");
    final http.Response response = await _httpClient.get(uri);
    if (response.statusCode != 200) {
      throw Exception("Health check failed: ${response.statusCode}");
    }
    return (jsonDecode(response.body) as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> syncStatus(String host) async {
    final Uri uri = Uri.parse("$host/sync/status");
    final http.Response response = await _httpClient.get(uri);
    if (response.statusCode != 200) {
      throw Exception("Sync status failed: ${response.statusCode}");
    }
    return (jsonDecode(response.body) as Map).cast<String, dynamic>();
  }

  Future<SyncEnvelope> push(String host, SyncEnvelope envelope) async {
    final Uri uri = Uri.parse("$host/sync/push");
    final http.Response response = await _httpClient.post(
      uri,
      headers: <String, String>{"content-type": "application/json"},
      body: jsonEncode(envelope.toJson()),
    );
    if (response.statusCode != 200) {
      throw Exception("Sync push failed: ${response.statusCode}: ${response.body}");
    }
    return SyncEnvelope.fromJson((jsonDecode(response.body) as Map).cast<String, dynamic>());
  }

  Future<SyncEnvelope> pull(String host, SyncEnvelope envelope) async {
    final Uri uri = Uri.parse("$host/sync/pull");
    final http.Response response = await _httpClient.post(
      uri,
      headers: <String, String>{"content-type": "application/json"},
      body: jsonEncode(envelope.toJson()),
    );
    if (response.statusCode != 200) {
      throw Exception("Sync pull failed: ${response.statusCode}: ${response.body}");
    }
    return SyncEnvelope.fromJson((jsonDecode(response.body) as Map).cast<String, dynamic>());
  }
}

