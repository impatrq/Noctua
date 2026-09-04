import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'https://nyctus.onrender.com';

  static Future<Map<String, dynamic>> obtenerAnalisis() async {
    final response = await http.get(
      Uri.parse('$baseUrl/analisis'),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }

    throw Exception(
      'Error ${response.statusCode}: ${response.body}',
    );
  }

  static Future<List<Map<String, dynamic>>> obtenerHistorial() async {
    final response = await http.get(
      Uri.parse('$baseUrl/historial'),
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.cast<Map<String, dynamic>>();
    }

    throw Exception(
      'Error ${response.statusCode}: ${response.body}',
    );
  }
}