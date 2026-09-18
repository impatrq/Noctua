import 'dart:convert';

import 'package:http/http.dart' as http;


class ApiService {

  // ==========================================================
  // URL DE RENDER
  // ==========================================================

  static const String baseUrl =
      'https://nyctus.onrender.com';


  // ==========================================================
  // OBTENER ÚLTIMO ANÁLISIS
  // ==========================================================

  static Future<Map<String, dynamic>>
      obtenerAnalisis() async {

    final response = await http.get(

      Uri.parse(
        '$baseUrl/analisis',
      ),

    ).timeout(
      const Duration(
        seconds: 20,
      ),
    );


    if (response.statusCode == 200) {

      final datos =
          jsonDecode(response.body);


      return Map<String, dynamic>.from(
        datos,
      );
    }


    throw Exception(
      'Error ${response.statusCode} al obtener el análisis',
    );
  }


  // ==========================================================
  // OBTENER HISTORIAL
  // ==========================================================

  static Future<List<Map<String, dynamic>>>
      obtenerHistorial() async {

    final response = await http.get(

      Uri.parse(
        '$baseUrl/historial',
      ),

    ).timeout(
      const Duration(
        seconds: 20,
      ),
    );


    if (response.statusCode == 200) {

      final datos =
          jsonDecode(response.body);


      return List<Map<String, dynamic>>.from(
        datos.map(
          (elemento) =>
              Map<String, dynamic>.from(
            elemento,
          ),
        ),
      );
    }


    throw Exception(
      'Error ${response.statusCode} al obtener el historial',
    );
  }


  // ==========================================================
  // SOLICITAR NUEVO ANÁLISIS
  // ==========================================================

  static Future<bool>
      nuevoAnalisis() async {

    final response = await http.post(

      Uri.parse(
        '$baseUrl/nuevo-analisis',
      ),

    ).timeout(
      const Duration(
        seconds: 20,
      ),
    );


    if (response.statusCode == 200) {

      return true;
    }


    return false;
  }
}