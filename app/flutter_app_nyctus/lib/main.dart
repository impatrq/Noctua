import 'package:flutter/material.dart';
import 'services/api_service.dart';

void main() {
  runApp(const NereasApp());
}

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


  @override
  void initState() {

    super.initState();

    cargarDatos();
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


  @override
  Widget build(BuildContext context) {

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

                          '$ganado',

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

                    mensajeEstado.isEmpty
                        ? 'Datos obtenidos del servidor'
                        : mensajeEstado,

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


  @override
  void initState() {

    super.initState();

    cargarHistorial();
  }


  // ========================================================
  // CARGAR HISTORIAL
  // ========================================================

  Future<void> cargarHistorial()
      async {

    setState(() {
      cargando = true;
    });


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
                                        '⏱ ${video['duracion'] ?? 0} segundos',
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

                                        final videoUrl =
                                            video['video'];


                                        if (videoUrl !=
                                            null) {

                                          ScaffoldMessenger
                                              .of(context)
                                              .showSnackBar(

                                            SnackBar(

                                              content:
                                                  Text(

                                                'Video disponible: $videoUrl',
                                              ),
                                            ),
                                          );
                                        }
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