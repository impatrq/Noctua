
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'https://nyctus.onrender.com';

  static Future<Map<String, dynamic>> obtenerAnalisis() async {
    final response = await http
        .get(Uri.parse('$baseUrl/analisis'))
        .timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(jsonDecode(response.body));
    }

    throw Exception('Error ${response.statusCode} al obtener el análisis');
  }

  static Future<Map<String, dynamic>> obtenerEstado() async {
    final response = await http
        .get(Uri.parse('$baseUrl/estado'))
        .timeout(const Duration(seconds: 15));

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(jsonDecode(response.body));
    }

    throw Exception('Error ${response.statusCode} al consultar el estado');
  }

  static Future<List<Map<String, dynamic>>> obtenerHistorial() async {
    final response = await http
        .get(Uri.parse('$baseUrl/historial'))
        .timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      final datos = jsonDecode(response.body);

      return List<Map<String, dynamic>>.from(
        datos.map((elemento) => Map<String, dynamic>.from(elemento)),
      );
    }

    throw Exception('Error ${response.statusCode} al obtener el historial');
  }

  static Future<bool> nuevoAnalisis() async {
    final response = await http
        .post(Uri.parse('$baseUrl/nuevo-analisis'))
        .timeout(const Duration(seconds: 20));

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
