# 02 - 新闻处理与聚类逻辑

## 1. 核心组件

*(基于代码分析)*

- **`AppService`**: (当前) *可能*调用 `NewsClusterer` (需要确认调用点)，并将结果用于 UI 展示。
- **`NewsStorage`**: 提供待聚类的新闻数据 (通常通过 `AppService` 间接提供)。
- **`NewsClusterer`**: 实现基于 TF-IDF 和 DBSCAN 的新闻聚类，以及基于关键词的初步分类。

## 2. 关键流程

*(基于 `NewsClusterer` 的代码分析)*

1.  **输入**: `NewsClusterer.cluster()` 方法接收新闻列表 (`List[Dict]`) 作为输入。
2.  **文本准备**: 将每条新闻的 `title` 和 `content` 合并为一个文本字符串。
3.  **特征提取 (TF-IDF)**:
    -   使用 `scikit-learn` 的 `TfidfVectorizer` 将文本列表转换为 TF-IDF 矩阵。
    -   参数: `max_features=5000`, `stop_words='english'` (英文停用词，对中文文本可能效果不佳，需要注意)。
4.  **聚类 (DBSCAN)**:
    -   使用 `scikit-learn` 的 `DBSCAN` 对 TF-IDF 矩阵进行聚类。
    -   参数: `metric='cosine'` (使用余弦相似度), `eps` (邻域半径，默认 0.5), `min_samples` (核心点最小样本数，默认 2)。这些参数可通过 `set_clustering_params` 修改。
5.  **结果处理**: 遍历 DBSCAN 返回的标签 (`clustering.labels_`):
    -   标签为 `-1` 的视为噪声点，被忽略。
    -   对于每个有效标签 (簇 ID):
        -   如果该标签对应的事件字典 (`events[label]`) 不存在，则创建它。
            -   使用簇中第一个新闻的信息初始化事件的 `title`, `summary` (使用 `_generate_summary`), `keywords` (使用 `_extract_keywords`), `category` (使用 `_categorize_news`) 和 `publish_time`。
            -   初始化 `reports` (空列表) 和 `sources` (空集合)。
        -   将当前新闻字典添加到事件的 `reports` 列表中。
        -   将新闻来源 (`source_name`) 添加到事件的 `sources` 集合中。
        -   *更新逻辑*: 如果同一来源的新闻已存在于事件中，会比较发布时间，并保留较新的一个。
        -   更新事件的 `publish_time` 为其包含的所有报道中的最早时间。
6.  **输出准备**: 将每个事件字典中的 `sources` 集合转换为列表 (便于 JSON 序列化)。
7.  **排序**: 按每个事件包含的报道数量 (`len(x["reports"])`) 对事件列表进行降序排序。
8.  **输出**: 返回事件列表 (`List[Dict]`)。

**辅助流程:**

-   **初步分类 (`_categorize_news`)**: 在创建事件时调用，用于为事件设置初始分类。
    -   合并新闻的 `title` 和 `content`。
    -   遍历预定义的 `self.category_keywords` 字典。
    -   检查文本中是否包含各分类的关键词。
    -   优先匹配标题中的关键词，若无则匹配内容中的第一个关键词。
    -   返回分类 ID (如 `politics`, `technology`) 或 `uncategorized`。
-   **摘要生成 (`_generate_summary`)**: 使用新闻内容的前 200 个字符，并尝试在句尾断开。
-   **关键词提取 (`_extract_keywords`)**: 简单地分割标题，移除标点和一些基础停用词，返回前 5 个长度大于 1 的词。

## 3. 算法与参数

-   **TF-IDF**: `TfidfVectorizer(max_features=5000, stop_words='english')`
    -   `max_features`: 限制词汇表大小。
    -   `stop_words`: 使用英文停用词，可能需要针对中文优化。
-   **DBSCAN**: `DBSCAN(eps=0.5, min_samples=2, metric='cosine')`
    -   `eps`: 邻域半径，影响簇的发现范围，对结果敏感。
    -   `min_samples`: 形成簇所需的最小样本数，影响噪声点判断。
    -   `metric`: 使用余弦距离计算样本间距离。
-   **分类**: 基于 `self.category_keywords` 中的关键词列表进行硬匹配。

## 4. 待确认/优化点

-   **调用时机**: `NewsClusterer.cluster` 方法在何时被 `AppService` 或其他组件调用？是实时触发还是后台批处理？
-   **去重**: 代码中未明确看到独立的去重步骤，去重逻辑可能在 `AppService` 的刷新流程中处理，或者隐含在 DBSCAN 的聚类过程中 (相似项聚在一起)。
-   **中文处理**: TF-IDF 的 `stop_words='english'` 对中文无效。关键词提取 (`_extract_keywords`) 使用简单的空格分割，对中文效果差。需要引入中文分词库 (如 `jieba`) 并使用中文停用词表。
-   **参数调优**: DBSCAN 的 `eps` 和 `min_samples` 需要根据实际数据进行调优才能获得理想的聚类效果。
-   **性能**: 对于大量新闻，TF-IDF 计算和 DBSCAN 聚类可能会有性能瓶颈。
-   **事件代表性**: 事件的 `title`, `summary`, `keywords` 当前仅基于簇中的*第一个*新闻生成，可能不够全面或准确。可以考虑融合簇内所有新闻的信息。 