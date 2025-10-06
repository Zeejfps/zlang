using ParserModule.Nodes;

namespace ParserModule;

public interface IAstNodeVisitor
{
    void VisitPrimaryExpressionNode(PrimaryExpressionNode primaryExpressionNode);
}