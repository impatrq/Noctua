
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class ApiService {
  static const int puertoDescubrimiento = 37020;
  static const String mensajeDescubrimiento = 'NYCTUS_DISCOVER';

  static String? _baseUrl;

  // Conserva compatibilidad con las pantallas que usan ApiService.baseUrl.
  // Se actualiza automáticamente cuando se encuentra el servidor.
  static String get baseUrl => _baseUrl ?? '';

  // Permite obtener la dirección antes de construir una URL de video.
  static Future<String> obtenerBaseUrl() async {
    final actual = _baseUrl;
    if (actual != null) return actual;

    final encontrada = await _descubrirServidor();

    if (encontrada == null) {
      throw Exception('No se encontró el servidor NYCTUS en la red local');
    }

    return encontrada;
  }

  // Busca la PC mediante UDP Broadcast.
  static Future<String?> _descubrirServidor() async {
    RawDatagramSocket? socket;

    try {
      socket = await RawDatagramSocket.bind(
        InternetAddress.anyIPv4,
        0,
      );

      socket.broadcastEnabled = true;

      final resultado = Completer<String?>();

      socket.listen((evento) {
        if (evento != RawSocketEvent.read) return;

        Datagram? datagrama;

        while ((datagrama = socket!.receive()) != null) {
          try {
            final respuesta = jsonDecode(
              utf8.decode(datagrama!.data),
            );

            if (respuesta['service'] == 'nyctus' &&
                respuesta['host'] != null &&
                respuesta['port'] != null) {
              final host = respuesta['host'];
              final puerto = respuesta['port'];

              final url = 'http://$host:$puerto';

              if (!resultado.isCompleted) {
                resultado.complete(url);
              }

              break;
            }
          } catch (_) {
            // Ignora paquetes que no tengan el formato esperado.
          }
        }
      });

      final mensaje = utf8.encode(mensajeDescubrimiento);

      socket.send(
        mensaje,
        InternetAddress('255.255.255.255'),
        puertoDescubrimiento,
      );

      final encontrada = await resultado.future.timeout(
        const Duration(seconds: 4),
        onTimeout: () => null,
      );

      if (encontrada != null) {
        _baseUrl = encontrada;
        print('[NYCTUS] Servidor encontrado: $_baseUrl');
      }

      return encontrada;
    } catch (error) {
      print('[NYCTUS] Error buscando el servidor: $error');
      return null;
    } finally {
      socket?.close();
    }
  }

  // Ejecuta una petición y vuelve a descubrir el servidor si se pierde
  // la conexión con la dirección que estaba guardada.
  static Future<http.Response> _solicitar(
    Future<http.Response> Function(String url) peticion,
  ) async {
    String? url = _baseUrl;

    if (url == null) {
      url = await _descubrirServidor();
    }

    if (url == null) {
      throw Exception(
        'No se pudo encontrar el servidor NYCTUS. '
        'Comprobá que los dispositivos estén en la misma red.',
      );
    }

    try {
      return await peticion(url);
    } catch (_) {
      print('[NYCTUS] Se perdió la conexión. Buscando nuevamente...');

      _baseUrl = null;
      final nuevaUrl = await _descubrirServidor();

      if (nuevaUrl == null) {
        throw Exception('No se pudo recuperar la conexión con NYCTUS');
      }

      return await peticion(nuevaUrl);
    }
  }

  static Future<Map<String, dynamic>> obtenerAnalisis() async {
    final response = await _solicitar(
      (url) => http
          .get(Uri.parse('$url/analisis'))
          .timeout(const Duration(seconds: 20)),
    );

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(jsonDecode(response.body));
    }

    throw Exception('Error ${response.statusCode} al obtener el análisis');
  }

  static Future<Map<String, dynamic>> obtenerEstado() async {
    final response = await _solicitar(
      (url) => http
          .get(Uri.parse('$url/estado'))
          .timeout(const Duration(seconds: 15)),
    );

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(jsonDecode(response.body));
    }

    throw Exception('Error ${response.statusCode} al consultar el estado');
  }

  static Future<List<Map<String, dynamic>>> obtenerHistorial() async {
    final response = await _solicitar(
      (url) => http
          .get(Uri.parse('$url/historial'))
          .timeout(const Duration(seconds: 20)),
    );

    if (response.statusCode == 200) {
      final datos = jsonDecode(response.body);

      return List<Map<String, dynamic>>.from(
        datos.map(
          (elemento) => Map<String, dynamic>.from(elemento),
        ),
      );
    }

    throw Exception('Error ${response.statusCode} al obtener el historial');
  }

  static Future<bool> nuevoAnalisis() async {
    final response = await _solicitar(
      (url) => http
          .post(Uri.parse('$url/nuevo-analisis'))
          .timeout(const Duration(seconds: 20)),
    );

    if (response.statusCode == 200) {
      return true;
    }

    if (response.statusCode == 409) {
      throw Exception('Ya existe un análisis en curso');
    }

    throw Exception(
      'No se pudo solicitar el análisis. Código: ${response.statusCode}',
    );
  }
}
