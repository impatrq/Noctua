import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static Future<Map<String, dynamic>> obtenerAnalisis() async {
    final response = await http.get(
      Uri.parse('http://10.0.2.2:8000/analisis'),
    );

    return jsonDecode(response.body);
  }
}