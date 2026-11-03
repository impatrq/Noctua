import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

import 'api_service.dart';

/// Guarda el historial y los videos procesados en el almacenamiento del
/// propio celular.
///
/// Por qué existe: Render guarda todo en memoria (y los archivos en un
/// disco que tampoco es permanente), así que cuando el servicio se
/// reinicia -por inactividad o por un deploy nuevo- se pierde todo. Este
/// servicio hace que, apenas la app ve un análisis nuevo, descargue el
/// video y lo guarde en el teléfono. Así, aunque Render lo borre después,
/// el celular ya se quedó con su propia copia.
class LocalHistorialService {
  LocalHistorialService._();
  static final LocalHistorialService instancia = LocalHistorialService._();

  static const String _nombreIndice = 'historial_local.json';

  Future<Directory> _carpetaBase() async {
    final docs = await getApplicationDocumentsDirectory();
    final carpeta = Directory('${docs.path}/nyctus_historial');
    if (!await carpeta.exists()) {
      await carpeta.create(recursive: true);
    }
    return carpeta;
  }

  Future<File> _archivoIndice() async {
    final carpeta = await _carpetaBase();
    return File('${carpeta.path}/$_nombreIndice');
  }

  /// Lee lo que ya está guardado en el celular, sin tocar la red. Útil
  /// para mostrar algo de inmediato al abrir la pantalla, incluso sin
  /// conexión.
  Future<List<Map<String, dynamic>>> cargarLocal() async {
    final archivo = await _archivoIndice();

    if (!await archivo.exists()) return [];

    try {
      final contenido = await archivo.readAsString();
      final datos = jsonDecode(contenido) as List;
      return datos.map((e) => Map<String, dynamic>.from(e)).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _guardarIndice(List<Map<String, dynamic>> entradas) async {
    final archivo = await _archivoIndice();
    await archivo.writeAsString(jsonEncode(entradas));
  }

  /// Compara el historial local con el que tiene Render ahora mismo.
  /// Descarga a disco cualquier video procesado que todavía no tengamos
  /// guardado, y actualiza el índice local. Devuelve la lista completa
  /// (ya combinada) para mostrar en la pantalla.
  Future<List<Map<String, dynamic>>> sincronizar() async {
    final local = await cargarLocal();

    // Un análisis ya guardado se identifica por el nombre del archivo de
    // video (el backend genera uno único por fecha).
    final yaGuardados = local
        .map((e) => e['video'] as String?)
        .whereType<String>()
        .toSet();

    List<Map<String, dynamic>> remoto;

    try {
      remoto = await ApiService.obtenerHistorial();
    } catch (_) {
      // Sin conexión con Render: mostramos lo que ya teníamos guardado.
      return local;
    }

    final carpeta = await _carpetaBase();
    bool huboNuevos = false;

    for (final item in remoto) {
      final nombreVideo = item['video'] as String?;

      if (nombreVideo == null || nombreVideo.isEmpty) {
        // Análisis sin video procesado todavía: lo guardamos para no
        // perder el conteo, pero sin archivo local asociado.
        final yaExiste = local.any(
          (e) => e['fecha'] == item['fecha'] && e['video'] == null,
        );
        if (!yaExiste) {
          local.insert(0, Map<String, dynamic>.from(item));
          huboNuevos = true;
        }
        continue;
      }

      if (yaGuardados.contains(nombreVideo)) continue;

      try {
        final url = '${ApiService.baseUrl}/video-analisis/$nombreVideo';
        final respuesta = await http
            .get(Uri.parse(url))
            .timeout(const Duration(seconds: 60));

        if (respuesta.statusCode == 200) {
          final rutaLocal = '${carpeta.path}/$nombreVideo';
          await File(rutaLocal).writeAsBytes(respuesta.bodyBytes);

          final entrada = Map<String, dynamic>.from(item);
          entrada['archivo_local'] = rutaLocal;

          local.insert(0, entrada);
          yaGuardados.add(nombreVideo);
          huboNuevos = true;
        }
      } catch (_) {
        // Si falla la descarga de este video puntual, seguimos con los
        // demás; se reintenta solo en la próxima sincronización.
      }
    }

    if (huboNuevos) {
      local.sort((a, b) {
        final fa =
            DateTime.tryParse(a['fecha']?.toString() ?? '') ?? DateTime(2000);
        final fb =
            DateTime.tryParse(b['fecha']?.toString() ?? '') ?? DateTime(2000);
        return fb.compareTo(fa);
      });

      await _guardarIndice(local);
    }

    return local;
  }
}