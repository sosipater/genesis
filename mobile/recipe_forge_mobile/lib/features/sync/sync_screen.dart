import "package:flutter/material.dart";

import "../../config/app_config.dart";
import "../../data/db/app_database.dart";
import "sync_controller.dart";

class SyncScreen extends StatefulWidget {
  final SyncController controller;
  final VoidCallback onSyncComplete;

  const SyncScreen({
    super.key,
    required this.controller,
    required this.onSyncComplete,
  });

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  late final TextEditingController _hostController;

  @override
  void initState() {
    super.initState();
    _hostController = TextEditingController();
    widget.controller.addListener(_onChanged);
    widget.controller.load();
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChanged);
    _hostController.dispose();
    super.dispose();
  }

  void _onChanged() {
    if (!mounted) {
      return;
    }
    _hostController.text = widget.controller.host;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          TextField(
            controller: _hostController,
            decoration: const InputDecoration(
              labelText: "Desktop Host URL",
              hintText: "http://192.168.1.100:8765",
            ),
            onChanged: widget.controller.updateHost,
          ),
          const SizedBox(height: 16),
          Row(
            children: <Widget>[
              ElevatedButton(
                onPressed: widget.controller.running
                    ? null
                    : () async {
                        final result = await widget.controller.testConnection();
                        if (!context.mounted) {
                          return;
                        }
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result.message)));
                      },
                child: const Text("Test Connection"),
              ),
              const SizedBox(width: 12),
              ElevatedButton(
                onPressed: widget.controller.running
                    ? null
                    : () async {
                        final result = await widget.controller.syncNow();
                        widget.onSyncComplete();
                        if (!context.mounted) {
                          return;
                        }
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result.message)));
                      },
                child: const Text("Sync Now"),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (widget.controller.running) const LinearProgressIndicator(),
          const SizedBox(height: 12),
          Text("Last Status: ${widget.controller.lastStatus ?? "N/A"}"),
          const SizedBox(height: 8),
          Text("Last Sync At: ${widget.controller.lastSyncAtUtc ?? "Never"}"),
          const SizedBox(height: 16),
          const Divider(),
          Text("App: ${kAppConfig.appId}"),
          Text("Version: ${kAppConfig.appVersion}"),
          const Text("Schema: ${AppDatabase.schemaVersion}"),
          Text("Sync Protocol: ${kAppConfig.syncProtocolVersion}"),
          Text("Share Format: ${kAppConfig.recipeShareFormatVersion}"),
          const SizedBox(height: 16),
          Text(
            "Tip: the desktop app can save a full backup zip from the toolbar. Sync keeps devices aligned; backups are an extra safety net for your library.",
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

