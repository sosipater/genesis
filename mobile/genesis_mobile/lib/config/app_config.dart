class AppConfig {
  final String appId;
  final String appVersion;
  final int syncProtocolVersion;
  final int recipeShareFormatVersion;
  final String defaultHost;

  const AppConfig({
    required this.appId,
    required this.appVersion,
    required this.syncProtocolVersion,
    required this.recipeShareFormatVersion,
    required this.defaultHost,
  });
}

const AppConfig kAppConfig = AppConfig(
  appId: "genesis-mobile",
  appVersion: "0.2.0",
  syncProtocolVersion: 1,
  recipeShareFormatVersion: 1,
  defaultHost: "http://127.0.0.1:8765",
);

