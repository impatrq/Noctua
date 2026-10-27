import 'dart:async';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'services/api_service.dart';

void main() {
  runApp(const NereasApp());
}

// Tiempo a partir del cual un análisis se considera "viejo" y el contador
// de Inicio deja de mostrarlo, volviendo a 0. Ajustá este valor a lo que
// tenga sentido para el uso real (p. ej. la duración típica entre vuelos).
const Duration kTiempoExpiracionAnalisis = Duration(minutes: 20);

class NereasApp extends StatelessWidget {
  const NereasApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Nyctus',

      theme: ThemeData(
        brightness: Brightness.dark,

        scaffoldBackgroundColor:
            const Color(0xFF101820),

        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.dark,
        ),

        useMaterial3: true,
      ),

      home: const MainScreen(),
    );
  }
}


// ==========================================================
// PANTALLA PRINCIPAL
// ==========================================================

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() =>
      _MainScreenState();
}


class _MainScreenState
    extends State<MainScreen> {

  int paginaActual = 0;

  final paginas = const [
    HomeScreen(),
    HistoryScreen(),
    SettingsScreen(),
  ];


  @override
  Widget build(BuildContext context) {

    return Scaffold(

      body: IndexedStack(
        index: paginaActual,
        children: paginas,
      ),

      bottomNavigationBar:
          NavigationBar(

        selectedIndex:
            paginaActual,

        onDestinationSelected:
            (index) {

          setState(() {
            paginaActual = index;
          });

        },

        destinations: const [

          NavigationDestination(
            icon:
                Icon(Icons.home_outlined),

            selectedIcon:
                Icon(Icons.home),

            label: 'Inicio',
          ),

          NavigationDestination(
            icon:
                Icon(Icons.history_outlined),

            selectedIcon:
                Icon(Icons.history),

            label: 'Historial',
          ),

          NavigationDestination(
            icon:
                Icon(Icons.settings_outlined),

            selectedIcon:
                Icon(Icons.settings),

            label: 'Ajustes',
          ),
        ],
      ),
    );
  }
}


// ==========================================================
// INICIO
// ==========================================================

class HomeScreen
    extends StatefulWidget {

  const HomeScreen({
    super.key,
  });

  @override
  State<HomeScreen> createState() =>
      _HomeScreenState();
}


class _HomeScreenState
    extends State<HomeScreen> {

  int ganado = 0;

  bool cargando = true;

  bool solicitandoAnalisis = false;

  String mensajeEstado =
      '';

  // Fecha del último análisis que devolvió el servidor (para saber si
  // "venció" y hay que dejar de mostrarlo).
  DateTime? fechaUltimoAnalisis;

  // Refresca la pantalla cada tanto SOLO para reevaluar si el análisis
  // ya venció, sin golpear al servidor de nuevo.
  Timer? _timerExpiracion;


  @override
  void initState() {

    super.initState();

    cargarDatos();

    _timerExpiracion = Timer.periodic(
      const Duration(seconds: 30),
      (_) {
        if (mounted) setState(() {});
      },
    );
  }

  @override
  void dispose() {
    _timerExpiracion?.cancel();
    super.dispose();
  }


  // ========================================================
  // CARGAR DATOS DEL SERVIDOR
  // ========================================================

  Future<void> cargarDatos() async {

    if (!mounted) return;

    setState(() {
      cargando = true;
    });


    try {

      final datos =
          await ApiService.obtenerAnalisis();


      if (!mounted) return;


      setState(() {

        ganado =
            (datos['ganado'] ?? 0) as int;

        fechaUltimoAnalisis =
            DateTime.tryParse(
          (datos['fecha'] ?? '').toString(),
        );

        cargando = false;
      });


    } catch (e) {

      if (!mounted) return;


      setState(() {
        cargando = false;
      });


      debugPrint(
        "Error al conectar con la API: $e",
      );
    }
  }


  // ========================================================
  // SOLICITAR NUEVO ANÁLISIS
  // ========================================================

  Future<void> solicitarNuevoAnalisis()
      async {

    if (solicitandoAnalisis) {
      return;
    }


    setState(() {

      solicitandoAnalisis = true;

      mensajeEstado =
          'Solicitando análisis...';
    });


    try {

      final correcto =
          await ApiService.nuevoAnalisis();


      if (!mounted) return;


      if (correcto) {

        setState(() {

          mensajeEstado =
              'Análisis solicitado correctamente';
        });


        ScaffoldMessenger
            .of(context)
            .showSnackBar(

          const SnackBar(

            content: Text(
              'Nuevo análisis solicitado. '
              'El sistema comenzará a procesarlo.',
            ),

            duration:
                Duration(seconds: 4),
          ),
        );


      } else {

        setState(() {

          mensajeEstado =
              'No se pudo solicitar el análisis';
        });


        ScaffoldMessenger
            .of(context)
            .showSnackBar(

          const SnackBar(

            content: Text(
              'El servidor no pudo recibir la solicitud.',
            ),
          ),
        );
      }


    } catch (e) {

      if (!mounted) return;


      setState(() {

        mensajeEstado =
            'Error de conexión con el servidor';
      });


      ScaffoldMessenger
          .of(context)
          .showSnackBar(

        SnackBar(

          content: Text(
            'Error de conexión: $e',
          ),
        ),
      );


      debugPrint(
        "Error solicitando análisis: $e",
      );


    } finally {

      if (!mounted) return;


      setState(() {
        solicitandoAnalisis = false;
      });
    }
  }


  // ========================================================
  // ¿El último análisis ya "venció"?
  // ========================================================

  bool get analisisVencido {
    if (fechaUltimoAnalisis == null) return true;
    return DateTime.now().difference(fechaUltimoAnalisis!) >
        kTiempoExpiracionAnalisis;
  }


  @override
  Widget build(BuildContext context) {

    final mostrarVencido = !cargando && analisisVencido;
    final ganadoAMostrar = mostrarVencido ? 0 : ganado;

    return SafeArea(

      child: Padding(

        padding:
            const EdgeInsets.all(24),

        child: Column(

          children: [

            const SizedBox(
              height: 20,
            ),


            // =================================================
            // LOGO DE NYCTUS
            // =================================================

            ClipOval(

              child: Image.asset(

                'assets/logo.jpg',

                width: 180,

                height: 180,

                fit: BoxFit.cover,
              ),
            ),


            const SizedBox(
              height: 30,
            ),


            // =================================================
            // CONTADOR
            // =================================================

            Container(

              width:
                  double.infinity,

              padding:
                  const EdgeInsets.all(30),

              decoration:
                  BoxDecoration(

                color:
                    const Color(0xFF172635),

                borderRadius:
                    BorderRadius.circular(25),
              ),

              child: Column(

                children: [

                  const Text(

                    'Ganado detectado',

                    style:
                        TextStyle(

                      fontSize: 18,

                      color: Colors.grey,
                    ),
                  ),


                  const SizedBox(
                    height: 10,
                  ),


                  cargando

                      ? const CircularProgressIndicator()

                      : Text(

                          '$ganadoAMostrar',

                          style:
                              const TextStyle(

                            fontSize: 64,

                            fontWeight:
                                FontWeight.bold,

                            color:
                                Colors.blue,
                          ),
                        ),


                  const Text(

                    'cabezas',

                    style:
                        TextStyle(
                      fontSize: 18,
                    ),
                  ),


                  const SizedBox(
                    height: 15,
                  ),


                  Text(

                    mostrarVencido
                        ? 'Sin análisis reciente'
                        : (mensajeEstado.isEmpty
                            ? 'Datos obtenidos del servidor'
                            : mensajeEstado),

                    textAlign:
                        TextAlign.center,

                    style:
                        const TextStyle(

                      color:
                          Colors.grey,

                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),


            const SizedBox(
              height: 25,
            ),


            // =================================================
            // ACTUALIZAR DATOS
            // =================================================

            SizedBox(

              width:
                  double.infinity,

              height: 55,

              child:
                  ElevatedButton.icon(

                onPressed:
                    cargando
                        ? null
                        : cargarDatos,

                icon:
                    const Icon(
                  Icons.refresh,
                ),

                label:
                    const Text(
                  'Actualizar datos',
                ),
              ),
            ),


            const SizedBox(
              height: 12,
            ),


            // =================================================
            // NUEVO ANÁLISIS
            // =================================================

            SizedBox(

              width:
                  double.infinity,

              height: 55,

              child:
                  OutlinedButton.icon(

                onPressed:
                    solicitandoAnalisis
                        ? null
                        : solicitarNuevoAnalisis,

                icon:

                    solicitandoAnalisis

                        ? const SizedBox(

                            width: 20,

                            height: 20,

                            child:
                                CircularProgressIndicator(
                              strokeWidth: 2,
                            ),
                          )

                        : const Icon(
                            Icons.video_camera_back,
                          ),

                label:

                    Text(

                      solicitandoAnalisis

                          ? 'Solicitando...'

                          : 'Nuevo análisis',
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}


// ==========================================================
// HISTORIAL
// ==========================================================

class HistoryScreen
    extends StatefulWidget {

  const HistoryScreen({
    super.key,
  });

  @override
  State<HistoryScreen> createState() =>
      _HistoryScreenState();
}


class _HistoryScreenState
    extends State<HistoryScreen> {

  List<Map<String, dynamic>>
      videos = [];

  bool cargando = true;

  // Refresca el historial solo, sin que el usuario tenga que hacer nada,
  // así un video nuevo aparece mientras la app está abierta.
  Timer? _timerAutoRefresh;


  @override
  void initState() {

    super.initState();

    cargarHistorial();

    _timerAutoRefresh = Timer.periodic(
      const Duration(seconds: 10),
      (_) => cargarHistorial(mostrarCargando: false),
    );
  }

  @override
  void dispose() {
    _timerAutoRefresh?.cancel();
    super.dispose();
  }


  // ========================================================
  // CARGAR HISTORIAL
  // ========================================================

  Future<void> cargarHistorial({
    bool mostrarCargando = true,
  }) async {

    if (mostrarCargando) {

      setState(() {
        cargando = true;
      });
    }


    try {

      final datos =
          await ApiService.obtenerHistorial();


      if (!mounted) return;


      setState(() {

        videos = datos;

        cargando = false;
      });


    } catch (e) {

      if (!mounted) return;


      setState(() {
        cargando = false;
      });


      debugPrint(
        "Error al cargar historial: $e",
      );
    }
  }


  // ========================================================
  // FORMATEAR DURACIÓN (sin decimales interminables)
  // ========================================================

  String _formatearDuracion(dynamic valor) {

    final segundos = (valor is num)
        ? valor.toDouble()
        : double.tryParse(valor.toString()) ?? 0.0;

    return '${segundos.toStringAsFixed(1)} s';
  }


  @override
  Widget build(BuildContext context) {

    return SafeArea(

      child: Padding(

        padding:
            const EdgeInsets.all(20),

        child: Column(

          crossAxisAlignment:
              CrossAxisAlignment.start,

          children: [

            const SizedBox(
              height: 20,
            ),


            const Text(

              'Historial',

              style:
                  TextStyle(

                fontSize: 32,

                fontWeight:
                    FontWeight.bold,
              ),
            ),


            const SizedBox(
              height: 20,
            ),


            Expanded(

              child:

                  cargando

                      ? const Center(
                          child:
                              CircularProgressIndicator(),
                        )

                      : videos.isEmpty

                          ? const Center(

                              child: Text(

                                'Todavía no hay análisis registrados.',

                                style:
                                    TextStyle(
                                  color:
                                      Colors.grey,
                                ),
                              ),
                            )

                          : RefreshIndicator(

                              onRefresh:
                                  cargarHistorial,

                              child:
                                  ListView.builder(

                                itemCount:
                                    videos.length,

                                itemBuilder:
                                    (context, index) {

                                  final video =
                                      videos[index];

                                  // El backend guarda solo el nombre del
                                  // archivo (p. ej. "analisis_....mp4");
                                  // acá se arma la URL completa para
                                  // reproducirlo.
                                  final String? nombreArchivo =
                                      video['video'] as String?;


                                  return Card(

                                    margin:
                                        const EdgeInsets.only(
                                      bottom: 12,
                                    ),

                                    child:
                                        ListTile(

                                      leading:
                                          Container(

                                        width: 60,

                                        height: 60,

                                        decoration:
                                            BoxDecoration(

                                          color:
                                              Colors.grey.shade800,

                                          borderRadius:
                                              BorderRadius.circular(
                                            10,
                                          ),
                                        ),

                                        child:
                                            const Icon(

                                          Icons.play_arrow,

                                          color:
                                              Colors.blue,
                                        ),
                                      ),


                                      title:
                                          Text(

                                        video['fecha']
                                                ?.toString() ??
                                            'Sin fecha',
                                      ),


                                      subtitle:
                                          Text(

                                        '🐄 ${video['ganado'] ?? 0} cabezas\n'
                                        '👤 ${video['personas'] ?? 0} personas\n'
                                        '⏱ ${_formatearDuracion(video['duracion'] ?? 0)}',
                                      ),


                                      isThreeLine:
                                          true,


                                      trailing:
                                          const Icon(

                                        Icons
                                            .arrow_forward_ios,

                                        size: 16,
                                      ),


                                      onTap: () {

                                        if (nombreArchivo == null ||
                                            nombreArchivo.isEmpty) {

                                          ScaffoldMessenger
                                              .of(context)
                                              .showSnackBar(

                                            const SnackBar(
                                              content: Text(
                                                'Este análisis no tiene '
                                                'video procesado.',
                                              ),
                                            ),
                                          );

                                          return;
                                        }

                                        final videoUrl =
                                            '${ApiService.baseUrl}/video-analisis/$nombreArchivo';

                                        Navigator.of(context).push(
                                          MaterialPageRoute(
                                            builder: (_) =>
                                                VideoPlayerScreen(
                                              videoUrl: videoUrl,
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  );
                                },
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }
}


// ==========================================================
// REPRODUCTOR DE VIDEO (análisis procesado)
// ==========================================================

class VideoPlayerScreen extends StatefulWidget {

  final String videoUrl;

  const VideoPlayerScreen({
    super.key,
    required this.videoUrl,
  });

  @override
  State<VideoPlayerScreen> createState() =>
      _VideoPlayerScreenState();
}

class _VideoPlayerScreenState
    extends State<VideoPlayerScreen> {

  late final VideoPlayerController _controller;
  bool _error = false;

  @override
  void initState() {
    super.initState();

    _controller =
        VideoPlayerController.networkUrl(Uri.parse(widget.videoUrl))
          ..initialize().then((_) {
            if (!mounted) return;
            setState(() {});
            _controller.play();
          }).catchError((_) {
            if (!mounted) return;
            setState(() {
              _error = true;
            });
          });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Video del análisis')),
      body: Center(
        child: _error
            ? const Text(
                'No se pudo cargar el video.',
                style: TextStyle(color: Colors.grey),
              )
            : _controller.value.isInitialized
                ? AspectRatio(
                    aspectRatio: _controller.value.aspectRatio,
                    child: Stack(
                      alignment: Alignment.bottomCenter,
                      children: [
                        VideoPlayer(_controller),
                        VideoProgressIndicator(
                          _controller,
                          allowScrubbing: true,
                        ),
                      ],
                    ),
                  )
                : const CircularProgressIndicator(),
      ),
      floatingActionButton: _controller.value.isInitialized
          ? FloatingActionButton(
              onPressed: () {
                setState(() {
                  _controller.value.isPlaying
                      ? _controller.pause()
                      : _controller.play();
                });
              },
              child: Icon(
                _controller.value.isPlaying
                    ? Icons.pause
                    : Icons.play_arrow,
              ),
            )
          : null,
    );
  }
}


// ==========================================================
// AJUSTES
// ==========================================================

class SettingsScreen
    extends StatelessWidget {

  const SettingsScreen({
    super.key,
  });


  @override
  Widget build(BuildContext context) {

    return SafeArea(

      child: ListView(

        padding:
            const EdgeInsets.all(20),

        children: [

          const SizedBox(
            height: 20,
          ),


          const Text(

            'Ajustes',

            style:
                TextStyle(

              fontSize: 32,

              fontWeight:
                  FontWeight.bold,
            ),
          ),


          const SizedBox(
            height: 25,
          ),


          SwitchListTile(

            title:
                const Text(
              'Notificaciones',
            ),

            subtitle:
                const Text(
              'Recibir avisos de nuevos análisis',
            ),

            value: true,

            onChanged:
                (value) {},
          ),


          const Divider(),


          ListTile(

            leading:
                const Icon(
              Icons.cloud,
            ),

            title:
                const Text(
              'Sincronización',
            ),

            subtitle:
                const Text(
              'Conectado',
            ),

            onTap: () {},
          ),


          ListTile(

            leading:
                const Icon(
              Icons.info_outline,
            ),

            title:
                const Text(
              'Acerca de Nyctus',
            ),

            onTap: () {},
          ),
        ],
      ),
    );
  }
}