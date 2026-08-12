from agents import build_search_agents, build_reader_agents, writer_chain, critic_chain

def run_research_pipeline(topic: str) -> dict:
    
    state = {}

#search agent
    print("\n"+" ="*50)
    print("step 1: Search agent is working")
    print("="*50)    
    
    search_agent = build_search_agents()
    search_result = search_agent.invoke({

    "messages" : [("user", f"Find recent, reliable and detailed information about:{topic}")]
    })
    state ["search_results"] = search_result['messages'] [-1].content
    
    print("\n search result ", state ['search_results'])
    
    
#reader agent

    print("\n"+" ="*50)
    print("step 2: Reader agent is scraping top resources...")
    print("="*50)    
    
    reader_agent = build_reader_agents()
    reader_result = reader_agent.invoke({
        "messages" : [("user",
            f"Based on the following search results about '{topic}', "
            f"pick the most relevant URL and scrape it for deeper content.\n\n"
            f"Search Results:\n{state['search_results'][:800]}")]
    })

    state ["scraped_content"] = reader_result['messages'] [-1].content
    print("\nscraped content: \n", state ['scraped_content'])
    
    #writer chain
    
    print("\n"+" ="*50)
    print("step 3: Writer chain is generating a research report...")
    print("="*50)
    
    research_combined = (
        f"Search Results : \n{state['search_results']}\n\n"
        f"Detailed Scraped Content : \n{state['scraped_content']}"  
    )
    state["report"] = writer_chain.invoke({
        "topic" : topic,
        "research" : research_combined
    })
    
    print("\n final report: \n", state ["report"])
    
    #critic chain
    print("\n"+" ="*50)
    print("step 4: Critic is reviewing the report...")
    print("="*50)
    
    state["feedback"] = critic_chain.invoke({
        "report" : state["report"]
    })
    print("\n critic report \n", state['feedback'])
    
    return state


if __name__ == "__main__":
    topic = input("\n Enter a research topic:")
    run_research_pipeline(topic)