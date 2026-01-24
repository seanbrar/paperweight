import arxiv

from src.mocks.local_client import MockArxivClient


def test_mock_client():
    client = MockArxivClient()
    print("Mirror DB:", client.mirror_db_path)

    # 1. Test Golden Set ID
    search = arxiv.Search(id_list=["1706.03762"])
    results = list(client.results(search))
    print(f"Search by ID found {len(results)} results")
    if results:
        print("Title:", results[0].title)

    # 2. Test Category Search
    search_cat = arxiv.Search(query="cat:cs.AI")
    results_cat = list(client.results(search_cat))
    print(f"Search 'cat:cs.AI' found {len(results_cat)} results")

if __name__ == "__main__":
    test_mock_client()
