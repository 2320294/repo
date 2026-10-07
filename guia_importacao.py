import streamlit as st

def _card(titulo, subtitulo, svg, ok=True):
    cor="#16a34a" if ok else "#dc2626"
    selo="CORRETO" if ok else "EVITE"
    st.markdown(f"""<div style="border:1px solid #d8dee9;border-radius:12px;padding:12px;background:white">
<div style="display:flex;justify-content:space-between"><b>{titulo}</b><span style="background:{cor};color:white;padding:2px 8px;border-radius:12px;font-size:11px">{selo}</span></div>
<div style="font-size:12px;color:#667085;margin:5px 0 8px">{subtitulo}</div>
<svg viewBox="0 0 520 165" width="100%" height="165" style="background:#f8fafc;border-radius:8px">{svg}</svg></div>""",unsafe_allow_html=True)

def renderizar_guia_preparacao_planta():
    st.markdown("### 📐 Como preparar sua planta para o AutoElétrica")
    st.caption("Prepare o DXF conforme estas regras para que ambientes, portas e soleiras sejam reconhecidos corretamente.")
    with st.expander("📘 Ver passo a passo para preparar o DXF",expanded=False):
        st.markdown("#### 1. Crie as layers obrigatórias")
        st.markdown("""| Layer | Conteúdo |
|---|---|
| `IA_AMBIENTES` | Polilinhas fechadas delimitando cada ambiente |
| `IA_TEXTOS` | Nome dos ambientes em TEXT ou MTEXT |
| `IA_PORTAS` | Geometria das portas |
| `IA_SOLEIRAS` | Soleiras/passagens correspondentes às portas |""")
        st.info("Use exatamente esses nomes. As quatro layers são verificadas na importação.")

        st.markdown("#### 2. Feche o contorno de cada ambiente")
        a,b=st.columns(2)
        with a:_card("Ambiente fechado","Uma polilinha fechada por ambiente.",'<rect x="80" y="25" width="350" height="115" fill="none" stroke="#2563eb" stroke-width="4"/><text x="255" y="90" text-anchor="middle" font-family="Arial" font-size="23">SALA</text>')
        with b:_card("Contorno aberto","Não deixe frestas no perímetro.",'<path d="M80 140 L80 25 L430 25 L430 140 L300 140 M260 140 L80 140" fill="none" stroke="#dc2626" stroke-width="4"/><text x="255" y="90" text-anchor="middle" font-family="Arial" font-size="23">SALA</text><text x="280" y="155" text-anchor="middle" font-size="25" fill="#dc2626">×</text>',False)

        st.markdown("#### 3. Posicione o nome dentro do ambiente")
        a,b=st.columns(2)
        with a:_card("Texto dentro","TEXT ou MTEXT dentro da polilinha.",'<rect x="80" y="25" width="350" height="115" fill="none" stroke="#2563eb" stroke-width="4"/><text x="255" y="90" text-anchor="middle" font-family="Arial" font-size="23" fill="#16a34a">COZINHA</text>')
        with b:_card("Texto fora","Não deixe o nome fora do contorno.",'<rect x="80" y="20" width="350" height="105" fill="none" stroke="#2563eb" stroke-width="4"/><text x="255" y="155" text-anchor="middle" font-family="Arial" font-size="23" fill="#dc2626">COZINHA</text>',False)

        st.markdown("#### 4. Alinhe portas e soleiras")
        porta='<line x1="65" y1="45" x2="205" y2="45" stroke="#111827" stroke-width="5"/><line x1="315" y1="45" x2="455" y2="45" stroke="#111827" stroke-width="5"/><line x1="205" y1="45" x2="205" y2="145" stroke="#2563eb" stroke-width="4"/><path d="M205 145 A100 100 0 0 1 305 45" fill="none" stroke="#2563eb" stroke-width="3"/>'
        a,b=st.columns(2)
        with a:_card("Porta + soleira","A soleira coincide com a passagem.",porta+'<rect x="205" y="39" width="110" height="12" fill="#d946ef" opacity=".55" stroke="#a21caf" stroke-width="2"/>')
        with b:_card("Soleira deslocada","Não deixe a soleira afastada da porta.",porta+'<rect x="225" y="75" width="110" height="12" fill="#fecaca" stroke="#dc2626" stroke-width="2"/><text x="280" y="112" text-anchor="middle" font-size="28" fill="#dc2626">×</text>',False)

        st.markdown("#### 5. Salve/exporte em DXF")
        st.write("Confira a escala, mantenha os elementos nas layers obrigatórias e salve a planta em **DXF**.")
        st.markdown("#### 6. Cadastre e importe")
        st.write("Informe o nome do projeto na barra lateral, clique em **Cadastrar Projeto**, selecione-o e envie o DXF na etapa **⚙️ Parâmetros**.")
        st.markdown("#### ✅ Checklist antes de importar")
        st.markdown("""- [ ] `IA_AMBIENTES` contém polilinhas fechadas.
- [ ] `IA_TEXTOS` contém um nome dentro de cada ambiente.
- [ ] `IA_PORTAS` contém as portas.
- [ ] `IA_SOLEIRAS` contém as soleiras alinhadas às portas.
- [ ] A planta está em escala coerente.
- [ ] O arquivo foi salvo em DXF.""")
        st.warning("Se uma layer obrigatória estiver ausente ou vazia, o processamento poderá ser interrompido para evitar resultados baseados em geometria incompleta.")
