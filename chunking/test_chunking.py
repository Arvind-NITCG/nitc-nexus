from chunking import Chunking
from models import Strategy
from config import settings

SAMPLE_PAGES = [
    {
        "page_number": 1,
        "text": """
        Machine learning is a branch of artificial intelligence that enables systems to learn
        and improve from experience without being explicitly programmed. It focuses on developing
        algorithms that can access data, learn from it, and make decisions with minimal human
        intervention. The core idea is to allow machines to learn by themselves using data that
        has been provided to them. Machine learning algorithms are trained on datasets, and over
        time they improve their accuracy by detecting patterns in the data.

        Supervised learning is the most common type of machine learning. In supervised learning,
        the algorithm is trained on labeled data, meaning the desired output is already known for
        each training example. The model learns to map inputs to outputs by minimizing the
        difference between its predictions and the actual labels. Common supervised learning
        algorithms include linear regression, logistic regression, decision trees, support vector
        machines, and neural networks. These are used in applications such as spam detection,
        image classification, and medical diagnosis.

        Unsupervised learning deals with unlabeled data. The algorithm tries to find hidden
        structure or patterns within the data without any prior knowledge of what the output
        should look like. Clustering is the most well-known unsupervised technique, where the
        model groups similar data points together. Dimensionality reduction methods such as PCA
        and t-SNE are also widely used to compress data while preserving its structure.
        Unsupervised learning is often used in anomaly detection, customer segmentation, and
        recommendation systems.
        """,
    },
    {
        "page_number": 2,
        "text": """
        The global climate crisis has accelerated significantly over the past two decades.
        Rising greenhouse gas emissions, primarily carbon dioxide and methane, are trapping
        heat in the atmosphere and driving temperatures higher. The consequences are visible
        across every continent: melting polar ice caps, rising sea levels, more frequent
        extreme weather events, and widespread ecosystem disruption. Scientists warn that
        without immediate and dramatic reductions in fossil fuel consumption, the planet will
        cross critical tipping points from which recovery becomes increasingly difficult.

        Renewable energy is widely regarded as the most viable path toward decarbonization.
        Solar and wind power have seen dramatic cost reductions over the last decade, making
        them competitive with or cheaper than coal and natural gas in most markets. Offshore
        wind farms now generate electricity at scale previously thought impossible. Solar panel
        efficiency has improved from around ten percent in the 1980s to over twenty-five percent
        in modern commercial panels. Battery storage technology is solving the intermittency
        problem, allowing surplus energy generated during peak production to be stored and
        dispatched when demand is high.

        Key steps toward a sustainable energy future include:
        1. Phasing out coal-fired power plants by 2035 in developed nations.
        2. Investing heavily in grid infrastructure to support distributed generation.
        3. Electrifying transportation through subsidies for electric vehicles.
        4. Retrofitting buildings with insulation and heat pumps.
        5. Funding research into green hydrogen and next-generation nuclear.

        D e e p   s e a   m i n i n g for rare earth minerals presents a new environmental
        frontier that remains poorly understood. Proponents argue it is necessary to supply the
        lithium, cobalt, and nickel required for battery manufacturing at scale.
        """,
    },
    {
        "page_number": 3,
        "text": """
        The human immune system is a complex network of cells, tissues, and organs that work
        together to defend the body against harmful pathogens including bacteria, viruses,
        fungi, and parasites. It operates through two main branches: the innate immune system,
        which provides rapid but non-specific defence, and the adaptive immune system, which
        mounts targeted responses tailored to specific threats.

        When a pathogen enters the body, innate immune cells such as macrophages and neutrophils
        respond within minutes to hours. They engulf and destroy invaders through a process called
        phagocytosis and release signaling molecules known as cytokines that recruit additional
        immune cells to the site of infection. This rapid first response buys time for the adaptive
        immune system to prepare a more precise attack.

        The adaptive immune system relies on lymphocytes — B cells and T cells — which are produced
        in the bone marrow. B cells produce antibodies, proteins that bind specifically to antigens
        on the surface of pathogens, marking them for destruction. T cells either directly kill
        infected cells or coordinate the immune response by secreting cytokines. Crucially, after
        an infection is cleared, a subset of these lymphocytes persist as memory cells, enabling
        the body to respond far more rapidly and effectively should the same pathogen be encountered
        again. This immunological memory is the biological principle underlying vaccination.

        Autoimmune disorders occur when the immune system mistakenly attacks the body's own tissues.
        Conditions such as rheumatoid arthritis, lupus, and multiple sclerosis result from this
        misdirected immune activity. Treatments typically involve immunosuppressant drugs that
        dampen the immune response, though researchers are working on more targeted therapies that
        can quiet specific errant immune pathways without compromising overall immunity.
        """,
    },
]

OVERLAP_SIZE: dict = {
    Strategy.FIXED:           20,
    Strategy.SENTENCE:        2,
    Strategy.RECURSIVE:       20,
    Strategy.SEMANTIC:        0,
    Strategy.HYBRID_SEMANTIC: 0,
}

W = 62

def sep(char: str = "─") -> None:
    print(char * W)

def print_chunk(chunk) -> None:
    print(f"  Chunk {chunk.chunk_id:>3}  │  page {chunk.page}  │  {chunk.token_count} tokens")
    import textwrap
    for line in textwrap.wrap(chunk.content, width=70):
        print(f"  {line}")
    print()

def main() -> None:
    sep("═")
    print("  Active settings")
    sep()
    print(f"  semantic_model      : {settings.semantic_model}")
    print(f"  chunk_size          : {settings.chunk_size} words/tokens")
    print(f"  min_chunk_size      : {settings.min_chunk_size} tokens")
    print(f"  max_tokens          : {settings.max_tokens} tokens")
    print(f"  similarity_threshold: {settings.similarity_threshold}")
    print(f"  max_num_sentences   : {settings.max_num_sentences}")
    print(f"  max_depth           : {settings.max_depth}")
    sep("═")
    print()

    for strategy in Strategy:
        chunker = Chunking(strategy.value)
        overlap = OVERLAP_SIZE[strategy]
        chunks = chunker.chunk(SAMPLE_PAGES, overlap_size=overlap)

        sep("═")
        print(f"  Strategy : {strategy.value.upper()}")
        print(f"  Overlap  : {overlap} words")
        # sep("═")

        if not chunks:
            print("No chunks produced.\n")
            continue

        for chunk in chunks:
            print_chunk(chunk)

        token_counts = [c.token_count for c in chunks]
        sep()
        print(
            f"  Total chunks : {len(chunks)}\n"
            f"  Avg: {sum(token_counts) / len(token_counts):.1f} tokens"
            f"  Min: {min(token_counts)}"
            f"  Max: {max(token_counts)}"
        )       
        
        print()

if __name__ == "__main__":
    main()