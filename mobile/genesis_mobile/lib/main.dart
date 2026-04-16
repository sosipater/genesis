import "package:flutter/material.dart";

import "app/dependencies.dart";
import "app/mobile_app.dart";

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final AppDependencies dependencies = await AppDependencies.create();
  runApp(MobileApp(dependencies: dependencies));
}

