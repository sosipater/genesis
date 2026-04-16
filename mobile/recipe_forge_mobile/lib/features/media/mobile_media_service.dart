import "dart:io";

import "package:path/path.dart" as p;
import "package:sqflite/sqflite.dart";
import "package:uuid/uuid.dart";

import "../../data/models/recipe_models.dart";
import "../../data/repositories/recipe_repository.dart";

class MobileMediaService {
  final RecipeRepository _repository;
  final Uuid _uuid;

  MobileMediaService(this._repository, {Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  Future<MediaAsset> importFromPath({
    required String ownerType,
    required String ownerId,
    required String sourcePath,
  }) async {
    final File source = File(sourcePath);
    if (!source.existsSync()) {
      throw StateError("Media file not found: $sourcePath");
    }
    final String extension = p.extension(source.path).toLowerCase();
    final String mediaId = _uuid.v4();
    final String relativePath = p.join(ownerType, "$mediaId${extension.isEmpty ? ".bin" : extension}");
    final String dbRoot = p.dirname(await getDatabasesPath());
    final String mediaRoot = p.join(dbRoot, "media");
    final String destPath = p.join(mediaRoot, relativePath);
    await Directory(p.dirname(destPath)).create(recursive: true);
    await source.copy(destPath);
    final MediaAsset asset = MediaAsset(
      id: mediaId,
      ownerType: ownerType,
      ownerId: ownerId,
      fileName: p.basename(source.path),
      mimeType: _mimeFromExtension(extension),
      relativePath: relativePath,
    );
    await _repository.upsertMediaAsset(asset, updatedAtUtc: DateTime.now().toUtc().toIso8601String());
    return asset;
  }

  Future<void> remove(String mediaAssetId) async {
    final MediaAsset? asset = await _repository.getMediaAssetById(mediaAssetId);
    if (asset != null) {
      final String dbRoot = p.dirname(await getDatabasesPath());
      final String mediaRoot = p.join(dbRoot, "media");
      final String target = p.join(mediaRoot, asset.relativePath);
      final File file = File(target);
      if (file.existsSync()) {
        await file.delete();
      }
    }
    await _repository.deleteMediaAsset(mediaAssetId, DateTime.now().toUtc().toIso8601String());
  }

  String _mimeFromExtension(String extension) {
    switch (extension) {
      case ".jpg":
      case ".jpeg":
        return "image/jpeg";
      case ".png":
        return "image/png";
      case ".gif":
        return "image/gif";
      case ".webp":
        return "image/webp";
      default:
        return "application/octet-stream";
    }
  }
}
