// viacep.js

document.addEventListener('DOMContentLoaded', function() {
    // Pegando os elementos do formulário (verifique se os IDs batem com o seu HTML)
    const cepInput = document.getElementById('id_cep');
    const enderecoInput = document.getElementById('id_endereco');
    const bairroInput = document.getElementById('id_bairro');
    const cidadeInput = document.getElementById('id_cidade');
    const estadoInput = document.getElementById('id_estado');
    const numeroInput = document.getElementById('id_numero');

    // Mensagem de erro do CEP exibida logo abaixo do campo (substitui o alert)
    const mensagemCep = document.createElement('div');
    mensagemCep.id = 'id_cep_status';
    mensagemCep.className = 'field-error';
    mensagemCep.hidden = true;
    cepInput.parentNode.insertBefore(mensagemCep, cepInput.nextSibling);

    function mostrarErroCep(texto) {
        mensagemCep.textContent = texto;
        mensagemCep.hidden = false;
        cepInput.setAttribute('aria-invalid', 'true');
        FlowMigao.descreverCom(cepInput, mensagemCep.id, true);
        FlowMigao.anunciar(texto);
    }

    function limparErroCep() {
        mensagemCep.textContent = '';
        mensagemCep.hidden = true;
        cepInput.removeAttribute('aria-invalid');
        FlowMigao.descreverCom(cepInput, mensagemCep.id, false);
    }

    // Função que busca o CEP
    cepInput.addEventListener('blur', function() {
        // Remove tudo que não for número do CEP
        let cep = cepInput.value.replace(/\D/g, '');

        if (cep !== "") {
            // Expressão regular para validar o CEP
            let validacep = /^[0-9]{8}$/;

            if(validacep.test(cep)) {
                limparErroCep();
                // Exibe "..." enquanto carrega
                enderecoInput.value = "...";
                bairroInput.value = "...";
                cidadeInput.value = "...";
                estadoInput.value = "...";
                FlowMigao.anunciar('Buscando endereço pelo CEP...');

                // Chamada à API
                fetch(`https://viacep.com.br/ws/${cep}/json/`)
                    .then(response => response.json())
                    .then(data => {
                        if (!("erro" in data)) {
                            // Atualiza os campos com os dados da API
                            enderecoInput.value = data.logradouro;
                            bairroInput.value = data.bairro;
                            cidadeInput.value = data.localidade;
                            estadoInput.value = data.uf;

                            FlowMigao.anunciar(
                                `Endereço preenchido: ${data.logradouro}, ${data.bairro}, ` +
                                `${data.localidade} - ${data.uf}. Informe o número.`
                            );
                            // Coloca o cursor no campo de número para o usuário continuar
                            numeroInput.focus();
                        } else {
                            limparCampos();
                            mostrarErroCep("CEP não encontrado.");
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao buscar o CEP:', error);
                        limparCampos();
                        mostrarErroCep("Erro ao buscar o CEP. Preencha o endereço manualmente.");
                    });
            } else {
                mostrarErroCep("Formato de CEP inválido. Use 8 números, por exemplo 01001-000.");
            }
        } else {
            limparErroCep();
        }
    });

    function limparCampos() {
        enderecoInput.value = "";
        bairroInput.value = "";
        cidadeInput.value = "";
        estadoInput.value = "";
    }
});
