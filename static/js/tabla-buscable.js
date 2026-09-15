/**
 * Agrega buscador + paginación client-side a una tabla ya renderizada.
 *
 * inicializarTablaBuscable({
 *   inputId: 'buscarFormularios',       // input de texto
 *   filaSelector: '#tablaFormularios tbody tr',
 *   textoSelector: '.nombre-texto',     // opcional: dónde tomar el texto a buscar dentro de la fila
 *   porPagina: 10,
 *   contadorId: 'countFormularios',     // opcional: elemento donde mostrar "N resultados"
 *   paginacionId: 'pagFormularios',     // opcional: contenedor de los controles de paginación
 *   vacioId: 'emptyFormularios',        // opcional: elemento a mostrar cuando no hay resultados
 * })
 */
function inicializarTablaBuscable(opciones) {
    const {
        inputId,
        filaSelector,
        textoSelector = null,
        porPagina = 10,
        contadorId = null,
        paginacionId = null,
        vacioId = null,
    } = opciones;

    const input = inputId ? document.getElementById(inputId) : null;
    const filas = Array.from(document.querySelectorAll(filaSelector));
    const contador = contadorId ? document.getElementById(contadorId) : null;
    const paginacion = paginacionId ? document.getElementById(paginacionId) : null;
    const vacio = vacioId ? document.getElementById(vacioId) : null;

    let pagina = 1;

    function textoDeFila(fila) {
        const el = textoSelector ? fila.querySelector(textoSelector) : fila;
        return (el ? el.textContent : '').toLowerCase();
    }

    function aplicar() {
        const q = (input ? input.value : '').trim().toLowerCase();
        const filtradas = q ? filas.filter(f => textoDeFila(f).includes(q)) : filas;

        const totalPaginas = Math.max(1, Math.ceil(filtradas.length / porPagina));
        if (pagina > totalPaginas) pagina = totalPaginas;

        filas.forEach(f => { f.style.display = 'none'; });
        const desde = (pagina - 1) * porPagina;
        filtradas.slice(desde, desde + porPagina).forEach(f => { f.style.display = ''; });

        if (contador) {
            contador.textContent = `${filtradas.length} resultado${filtradas.length !== 1 ? 's' : ''}`;
        }
        if (vacio) {
            vacio.hidden = filtradas.length !== 0;
        }

        if (paginacion) {
            paginacion.innerHTML = '';
            if (totalPaginas > 1) {
                paginacion.appendChild(crearBotonPag('«', pagina === 1, () => { pagina = 1; aplicar(); }));
                paginacion.appendChild(crearBotonPag('‹', pagina === 1, () => { pagina--; aplicar(); }));

                const info = document.createElement('span');
                info.className = 'pag-info';
                info.textContent = `Página ${pagina} de ${totalPaginas}`;
                paginacion.appendChild(info);

                paginacion.appendChild(crearBotonPag('›', pagina === totalPaginas, () => { pagina++; aplicar(); }));
                paginacion.appendChild(crearBotonPag('»', pagina === totalPaginas, () => { pagina = totalPaginas; aplicar(); }));
            }
        }
    }

    function crearBotonPag(texto, deshabilitado, onClick) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-gray btn-sm pag-btn';
        btn.textContent = texto;
        btn.disabled = deshabilitado;
        btn.addEventListener('click', onClick);
        return btn;
    }

    if (input) {
        input.addEventListener('input', () => { pagina = 1; aplicar(); });
    }
    aplicar();

    return { refrescar: aplicar };
}
