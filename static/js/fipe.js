document.addEventListener('DOMContentLoaded', function() {
    const selectMarca = document.getElementById('id_marca');
    const selectModelo = document.getElementById('id_modelo');

    const BASE_URL = 'https://parallelum.com.br/fipe/api/v1/carros';

    // Valores já salvos (edição) ou devolvidos pelo servidor após erro de validação
    const marcaAtual = selectMarca.value;
    const modeloAtual = selectModelo.value;

    function criarOpcao(valor, texto) {
        const option = document.createElement('option');
        option.value = valor;
        option.textContent = texto;
        return option;
    }

    // Seleciona o valor salvo; se ele não existir na lista da FIPE, mantém como opção extra
    function selecionarValor(select, valor) {
        if (!valor) {
            return null;
        }
        let opcao = Array.from(select.options).find(o => o.value === valor);
        if (!opcao) {
            opcao = criarOpcao(valor, valor);
            select.appendChild(opcao);
        }
        opcao.selected = true;
        return opcao;
    }

    function carregarModelos(marcaCodigo, modeloSelecionado) {
        selectModelo.innerHTML = '<option value="">Carregando modelos...</option>';
        selectModelo.disabled = true;
        selectModelo.setAttribute('aria-busy', 'true');

        fetch(`${BASE_URL}/marcas/${marcaCodigo}/modelos`)
            .then(response => response.json())
            .then(dados => {
                selectModelo.innerHTML = '<option value="">Selecione o Modelo</option>';
                selectModelo.disabled = false;
                selectModelo.removeAttribute('aria-busy');

                dados.modelos.forEach(modelo => {
                    selectModelo.appendChild(criarOpcao(modelo.nome, modelo.nome));
                });
                selecionarValor(selectModelo, modeloSelecionado);
                // Só avisa quando o usuário trocou a marca (na edição o modelo já vem pronto)
                if (!modeloSelecionado) {
                    FlowMigao.anunciar(`${dados.modelos.length} modelos disponíveis para esta marca.`);
                }
            })
            .catch(error => {
                console.error('Erro ao carregar modelos:', error);
                selectModelo.innerHTML = '<option value="">Erro ao carregar</option>';
                selectModelo.disabled = false;
                selectModelo.removeAttribute('aria-busy');
                FlowMigao.anunciar('Erro ao carregar os modelos. Tente novamente mais tarde.');
                selecionarValor(selectModelo, modeloSelecionado);
            });
    }

    // 1. Carrega as marcas assim que a tela abre
    fetch(`${BASE_URL}/marcas`)
        .then(response => response.json())
        .then(marcas => {
            selectMarca.innerHTML = '<option value="">Selecione a Marca</option>';
            marcas.forEach(marca => {
                // Cria a opção. O 'value' é o nome que vai pro Banco de Dados.
                const option = criarOpcao(marca.nome, marca.nome);
                // Guarda o código da API em um atributo data escondido
                option.dataset.codigo = marca.codigo;
                selectMarca.appendChild(option);
            });

            // Edição: reposiciona a marca salva e carrega os modelos dela
            const opcaoMarca = selecionarValor(selectMarca, marcaAtual);
            if (opcaoMarca && opcaoMarca.dataset.codigo) {
                carregarModelos(opcaoMarca.dataset.codigo, modeloAtual);
            }
        })
        // Sem a API, os valores atuais enviados pelo servidor continuam no select
        .catch(error => {
            console.error('Erro ao carregar marcas:', error);
            FlowMigao.anunciar('Erro ao carregar a lista de marcas.');
        });

    // 2. Escuta quando o usuário escolhe uma marca
    selectMarca.addEventListener('change', function() {
        // Pega a opção que foi selecionada
        const selectedOption = selectMarca.options[selectMarca.selectedIndex];

        // Se escolheu algo, pega o código escondido para chamar a API de modelos
        if (selectedOption && selectedOption.value !== "" && selectedOption.dataset.codigo) {
            carregarModelos(selectedOption.dataset.codigo, null);
        } else {
            selectModelo.innerHTML = '<option value="">Selecione a Marca primeiro</option>';
            selectModelo.disabled = true;
        }
    });
});
